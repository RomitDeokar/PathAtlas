from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

Species = Literal['male', 'female']
Scheme = Literal['synapse_count', 'log', 'uniform']


class KnockoutRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path_id: str = Field(min_length=16, max_length=64, pattern=r'^[a-f0-9]+$')
    neuron_ids: list[str] = Field(min_length=1, max_length=20)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    controls: int = Field(default=100, ge=10, le=200)
