from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DeviceCreate(BaseModel):
    ip: str
    device_type: str
    username: str
    password: str
    port: int = 22


class DeviceUpdate(BaseModel):
    ip: Optional[str] = None
    device_type: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    port: Optional[int] = None


class DeviceResponse(BaseModel):
    id: int
    ip: str
    hostname: str
    device_type: str
    username: str
    port: int
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RunResponse(BaseModel):
    id: int
    device_id: int
    timestamp: datetime
    cpu: str
    memory: str
    uptime: str
    hostname: str
    status: str
    error: Optional[str] = None

    class Config:
        from_attributes = True


class AlertCreate(BaseModel):
    device_id: Optional[int] = None
    metric: str
    operator: str = ">"
    threshold: float
    enabled: bool = True
