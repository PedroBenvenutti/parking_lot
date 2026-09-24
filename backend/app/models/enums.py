from enum import StrEnum


class Effort(StrEnum):
    MOTO = "moto"
    CARRO = "carro"
    CAMINHAO = "caminhao"

    @property
    def spots_needed(self) -> int:
        return 2 if self is Effort.CAMINHAO else 1


class Priority(StrEnum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    URGENTE = "urgente"


class CarStatus(StrEnum):
    PATIO = "patio"
    ESTACIONADO = "estacionado"
    CONCLUIDO = "concluido"


class EventType(StrEnum):
    CREATED = "created"
    PARKED = "parked"
    MOVED_SPOT = "moved_spot"
    UPDATED = "updated"
    HAZARD_ON = "hazard_on"
    HAZARD_OFF = "hazard_off"
    RETURNED_TO_PATIO = "returned_to_patio"
    COMPLETED = "completed"
