"""Sensor platform for Bicing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_STATION_IDS
from .coordinator import BicingStationCoordinator
from .entity import BicingStationEntity
from .lib.bike_stations_api import StationStatus


@dataclass(frozen=True, kw_only=True)
class BicingSensorDescription(SensorEntityDescription):
    """Describe a Bicing sensor."""

    value_fn: Callable[[StationStatus], int]


SENSORS: tuple[BicingSensorDescription, ...] = (
    BicingSensorDescription(
        key="total_bikes",
        translation_key="total_bikes",
        icon="mdi:bicycle",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda station: station.bikes_available + station.ebikes_available,
    ),
    BicingSensorDescription(
        key="ebikes",
        translation_key="ebikes",
        icon="mdi:bicycle-electric",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda station: station.ebikes_available,
    ),
    BicingSensorDescription(
        key="mechanical_bikes",
        translation_key="mechanical_bikes",
        icon="mdi:bicycle",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda station: station.bikes_available,
    ),
    BicingSensorDescription(
        key="available_docks",
        translation_key="available_docks",
        icon="mdi:parking",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda station: station.docks_available,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bicing sensors."""
    coordinator = entry.runtime_data.coordinator
    stations = entry.options[CONF_STATION_IDS]

    async_add_entities(
        BicingStationSensor(coordinator, station_id, description)
        for station_id in stations
        for description in SENSORS
    )


class BicingStationSensor(BicingStationEntity, SensorEntity):
    """Represent one metric for a Bicing station."""

    entity_description: BicingSensorDescription

    def __init__(
        self,
        coordinator: BicingStationCoordinator,
        station_id: str,
        description: BicingSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, station_id)
        self.entity_description = description
        # Set the translation key explicitly so the entity registry always
        # stores the metric name (especially when upgrading existing entries).
        self._attr_translation_key = description.translation_key
        self._attr_unique_id = f"{station_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return whether the station data is available."""
        return super().available and bool(
            self.coordinator.data and self.station_id in self.coordinator.data
        )

    @property
    def native_value(self) -> int | None:
        """Return the current sensor value."""
        station = self.coordinator.data.get(self.station_id)
        if station is None:
            return None
        return self.entity_description.value_fn(station)
