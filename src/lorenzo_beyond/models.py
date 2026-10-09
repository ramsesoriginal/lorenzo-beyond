"""The part of D&D Beyond's character document this tool reads.

The document is large and undocumented. These models name only what is used, ignore the rest,
and are lenient about what may be missing, so a change somewhere else on the sheet never matters.
When something this tool *does* read changes shape, validation fails and says where.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class Damage(_Model):
    dice_string: str | None = None


class Property(_Model):
    name: str


class ItemDefinition(_Model):
    id: int
    name: str
    description: str | None = None
    weight: float | None = None
    bundle_size: int | None = None
    cost: float | None = None  # gold pieces
    weight_multiplier: float = 1.0  # what its contents weigh, as a share (a Bag of Holding: 0)
    is_container: bool = False
    capacity_weight: float | None = None
    rarity: str | None = None
    magic: bool = False
    can_attune: bool = False
    attunement_description: str | None = None
    filter_type: str | None = None
    type: str | None = None
    sub_type: str | None = None
    armor_class: int | None = None
    damage: Damage | None = None
    damage_type: str | None = None
    properties: list[Property] | None = None
    is_custom_item: bool = False


class InventoryItem(_Model):
    id: int
    quantity: int = 1
    equipped: bool = False
    is_attuned: bool = False
    container_entity_id: int | None = None
    definition: ItemDefinition


class CustomItem(_Model):
    id: int
    name: str
    description: str | None = None
    notes: str | None = None


class Currencies(_Model):
    cp: int = 0
    sp: int = 0
    ep: int = 0
    gp: int = 0
    pp: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.model_dump()


class Creature(_Model):
    name: str


class Character(_Model):
    id: int
    name: str
    inventory: list[InventoryItem] = Field(default_factory=list)
    custom_items: list[CustomItem] = Field(default_factory=list)
    currencies: Currencies = Field(default_factory=Currencies)
    creatures: list[Creature] = Field(default_factory=list)


class Envelope(_Model):
    """`{"success": true, "message": "...", "data": {...}}`, as the character service answers."""

    success: bool
    message: str | None = None
    data: Character | None = None
