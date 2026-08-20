"""Integration tests for NetLink setup and connectivity lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

from pynetlink import (
    EVENT_ACCESS_CODES_STATE,
    EVENT_BROWSER_STATE,
    EVENT_DESK_STATE,
    EVENT_DEVICE_INFO,
    EVENT_DISPLAY_STATE,
    EVENT_DISPLAYS_LIST,
    Desk,
    DeskState,
    NetlinkConnectionError,
)
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from custom_components.netlink.const import (
    DOMAIN,
    RECONCILIATION_INTERVAL,
    WEBSOCKET_DISCONNECT_GRACE,
)

from .conftest import DEVICE_ID, TOKEN, FakeNetlinkClient


def _states_for_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> list[State]:
    """Return all live entity states belonging to a config entry."""
    registry = er.async_get(hass)
    return [
        state
        for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id)
        if (state := hass.states.get(entry.entity_id)) is not None
    ]


def _state_by_unique_id(hass: HomeAssistant, platform: str, unique_id: str) -> State:
    """Return an entity state through the public entity registry."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def _expire_disconnect_grace(
    hass: HomeAssistant, client: FakeNetlinkClient
) -> None:
    """Disconnect and advance Home Assistant beyond the grace period."""
    await client.emit("disconnect")
    async_fire_time_changed(
        hass,
        datetime.now(UTC) + WEBSOCKET_DISCONNECT_GRACE + timedelta(seconds=1),
    )
    await hass.async_block_till_done()


async def test_setup_creates_healthy_entities(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """A config entry exposes the initial REST snapshot as HA entities."""
    assert setup_integration.state is ConfigEntryState.LOADED
    assert (
        float(_state_by_unique_id(hass, "sensor", f"{DEVICE_ID}_desk_height").state)
        == 75
    )
    assert (
        float(
            _state_by_unique_id(
                hass, "sensor", f"{DEVICE_ID}_display_1_brightness"
            ).state
        )
        == 40
    )
    assert all(
        state.state != STATE_UNAVAILABLE
        for state in _states_for_entry(hass, setup_integration)
    )


async def test_transient_disconnect_does_not_flap_entity_availability(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """Entities stay available when the WebSocket returns within the grace period."""
    await netlink_client.emit("disconnect")
    async_fire_time_changed(
        hass,
        datetime.now(UTC) + WEBSOCKET_DISCONNECT_GRACE - timedelta(seconds=1),
    )
    await hass.async_block_till_done()

    assert all(
        state.state != STATE_UNAVAILABLE
        for state in _states_for_entry(hass, setup_integration)
    )

    await netlink_client.emit("connect")
    await hass.async_block_till_done()

    assert all(
        state.state != STATE_UNAVAILABLE
        for state in _states_for_entry(hass, setup_integration)
    )


async def test_sustained_disconnect_makes_all_entities_unavailable(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """All coordinator entities become unavailable after the grace period."""
    await _expire_disconnect_grace(hass, netlink_client)

    states = _states_for_entry(hass, setup_integration)
    assert states
    assert all(state.state == STATE_UNAVAILABLE for state in states)


async def test_reconnect_restores_fresh_rest_state(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """Reconnect exposes a fresh REST snapshot before entities recover."""
    await _expire_disconnect_grace(hass, netlink_client)
    netlink_client.desk = Desk(
        capabilities={"supports": {"height": True}},
        inventory={},
        state=DeskState(height=92, mode="idle", moving=False, beep="on"),
    )

    await netlink_client.emit("connect")
    await hass.async_block_till_done()

    assert (
        float(_state_by_unique_id(hass, "sensor", f"{DEVICE_ID}_desk_height").state)
        == 92
    )
    assert all(
        state.state != STATE_UNAVAILABLE
        for state in _states_for_entry(hass, setup_integration)
    )


async def test_lifecycle_logs_once_without_credentials(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An outage and recovery each log once without exposing credentials."""
    caplog.clear()
    caplog.set_level(logging.INFO, logger="custom_components.netlink.coordinator")

    await _expire_disconnect_grace(hass, netlink_client)
    await netlink_client.emit("connect")
    await hass.async_block_till_done()

    lifecycle_records = [
        record
        for record in caplog.records
        if record.name == "custom_components.netlink.coordinator"
    ]
    assert len(lifecycle_records) == 2
    assert "WebSocket connection lost" in lifecycle_records[0].getMessage()
    assert "recovered" in lifecycle_records[1].getMessage()
    assert TOKEN not in caplog.text


async def test_failed_reconnect_refresh_keeps_entities_unavailable(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """A failed post-reconnect snapshot cannot restore availability."""
    await _expire_disconnect_grace(hass, netlink_client)
    netlink_client.rest_error = NetlinkConnectionError("REST unavailable")

    await netlink_client.emit("connect")
    await hass.async_block_till_done()

    assert all(
        state.state == STATE_UNAVAILABLE
        for state in _states_for_entry(hass, setup_integration)
    )


async def test_failed_display_refresh_keeps_entities_unavailable(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """A partial display failure makes the complete reconnect snapshot fail."""
    await _expire_disconnect_grace(hass, netlink_client)
    netlink_client.display_error = NetlinkConnectionError("Display unavailable")

    await netlink_client.emit("connect")
    await hass.async_block_till_done()

    assert all(
        state.state == STATE_UNAVAILABLE
        for state in _states_for_entry(hass, setup_integration)
    )


async def test_disconnected_push_cannot_publish_stale_state(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """A push received during an outage cannot revive stale entities."""
    await _expire_disconnect_grace(hass, netlink_client)

    await netlink_client.emit(
        EVENT_DESK_STATE,
        {
            "capabilities": {"supports": {"height": True}},
            "inventory": {},
            "state": {"height": 99, "mode": "idle", "moving": False},
        },
    )
    for event in (
        EVENT_DEVICE_INFO,
        EVENT_DISPLAY_STATE,
        EVENT_BROWSER_STATE,
        EVENT_ACCESS_CODES_STATE,
        EVENT_DISPLAYS_LIST,
    ):
        await netlink_client.emit(event, {})
    await hass.async_block_till_done()

    assert all(
        state.state == STATE_UNAVAILABLE
        for state in _states_for_entry(hass, setup_integration)
    )


async def test_periodic_reconciliation_repairs_a_missed_push(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """The low-frequency REST snapshot repairs state without a push event."""
    netlink_client.desk = Desk(
        capabilities={"supports": {"height": True}},
        inventory={},
        state=DeskState(height=88, mode="idle", moving=False, beep="on"),
    )

    async_fire_time_changed(
        hass,
        datetime.now(UTC) + RECONCILIATION_INTERVAL + timedelta(seconds=1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        float(_state_by_unique_id(hass, "sensor", f"{DEVICE_ID}_desk_height").state)
        == 88
    )


async def test_reconciliation_removes_absent_display_state(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """A display absent from an authoritative snapshot stops exposing live values."""
    netlink_client.display_summaries = []

    async_fire_time_changed(
        hass,
        datetime.now(UTC) + RECONCILIATION_INTERVAL + timedelta(seconds=1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        _state_by_unique_id(hass, "sensor", f"{DEVICE_ID}_display_1_brightness").state
        == "unknown"
    )
    assert (
        _state_by_unique_id(hass, "number", f"{DEVICE_ID}_display_1_brightness").state
        == "unknown"
    )
    assert (
        _state_by_unique_id(hass, "select", f"{DEVICE_ID}_display_1_source").state
        == "unknown"
    )
    assert (
        _state_by_unique_id(hass, "switch", f"{DEVICE_ID}_display_1_power").state
        == "unknown"
    )


async def test_periodic_reconciliation_recovers_after_temporary_rest_failure(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """A later reconciliation recovers after a temporary REST failure."""
    now = datetime.now(UTC)
    netlink_client.rest_error = NetlinkConnectionError("REST unavailable")

    async_fire_time_changed(
        hass,
        now + RECONCILIATION_INTERVAL + timedelta(seconds=1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert all(
        state.state == STATE_UNAVAILABLE
        for state in _states_for_entry(hass, setup_integration)
    )

    netlink_client.rest_error = None
    netlink_client.desk = Desk(
        capabilities={"supports": {"height": True}},
        inventory={},
        state=DeskState(height=91, mode="idle", moving=False, beep="on"),
    )
    async_fire_time_changed(
        hass,
        now + 2 * RECONCILIATION_INTERVAL + timedelta(seconds=2),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        float(_state_by_unique_id(hass, "sensor", f"{DEVICE_ID}_desk_height").state)
        == 91
    )
    assert all(
        state.state != STATE_UNAVAILABLE
        for state in _states_for_entry(hass, setup_integration)
    )


async def test_reconciliation_detects_a_silent_dead_connection(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """Reconciliation marks entities unavailable if disconnect was never emitted."""
    netlink_client.connected = False

    async_fire_time_changed(
        hass,
        datetime.now(UTC) + RECONCILIATION_INTERVAL + timedelta(seconds=1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert all(
        state.state == STATE_UNAVAILABLE
        for state in _states_for_entry(hass, setup_integration)
    )
