"""Base entity for Bicing."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BicingStationCoordinator


class BicingStationEntity(CoordinatorEntity[BicingStationCoordinator]):
    """Base entity for a Bicing station."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BicingStationCoordinator, station_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.station_id = str(station_id)
        station_info = coordinator.station_info.get(self.station_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.station_id)},
            name=station_info.name if station_info else f"Bicing {self.station_id}",
            manufacturer="Ajuntament de Barcelona",
            model="Bicing station",
        )
