"""Load billing products and per-tier features from config/products.yaml.

Parsing uses ``yaml.safe_load`` only (ADR 0001).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class _ProductModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    tier: str
    features: list[str]


class _ProductsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    products: list[_ProductModel]
    tier_features: dict[str, list[str]]


@dataclass(frozen=True)
class Product:
    """A purchasable product mapped to a tier and feature set."""

    product_id: str
    tier: str
    features: tuple[str, ...]


@dataclass(frozen=True)
class BillingCatalog:
    """The resolved billing catalog: products and per-tier features."""

    products: dict[str, Product]
    tier_features: dict[str, tuple[str, ...]]

    def product(self, product_id: str) -> Product | None:
        return self.products.get(product_id)

    def features_for_tier(self, tier: str) -> tuple[str, ...]:
        return self.tier_features.get(tier, ())


def load_catalog(path: Path) -> BillingCatalog:
    """Load and validate the billing catalog.

    Failure modes: ``FileNotFoundError`` if missing; ``pydantic.ValidationError``
    on malformed content; ``ValueError`` on a duplicate product id.
    """

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    parsed = _ProductsFile.model_validate(raw)
    products: dict[str, Product] = {}
    for item in parsed.products:
        if item.product_id in products:
            raise ValueError(f"duplicate product id: {item.product_id}")
        products[item.product_id] = Product(
            product_id=item.product_id,
            tier=item.tier,
            features=tuple(item.features),
        )
    tier_features = {tier: tuple(feats) for tier, feats in parsed.tier_features.items()}
    return BillingCatalog(products=products, tier_features=tier_features)
