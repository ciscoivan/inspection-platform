import hashlib
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from .database import Base

# 中国标准时间 (UTC+8)
CST = timezone(timedelta(hours=8))


def now_cst():
    return datetime.now(CST).replace(tzinfo=None)

# PBKDF2 参数
PBKDF2_ITERATIONS = 600_000
PBKDF2_HASH_LEN = 32


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS, PBKDF2_HASH_LEN)
    return salt.hex() + "$" + h.hex()


def verify_password(password: str, stored: str) -> bool:
    # PBKDF2 格式: "salt_hex$hash_hex"
    if "$" in stored:
        salt_hex, h_hex = stored.split("$", 1)
        try:
            h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS, PBKDF2_HASH_LEN)
            return h.hex() == h_hex
        except (ValueError, AttributeError):
            return False
    # 旧格式 (sha256(salt+password)) — 向后兼容, 登录成功后自动升级
    try:
        salt, h = stored.split("$", 1)
        if hashlib.sha256((salt + password).encode()).hexdigest() == h:
            return True  # 旧格式匹配, 不做自动升级 (需要写 DB)
    except (ValueError, AttributeError):
        pass
    return False


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_cst)


class CustomCommand(Base):
    __tablename__ = "custom_commands"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_type = Column(String(50), nullable=False)   # cisco_ios / huawei / ... 或 "all"
    command = Column(String(500), nullable=False)
    description = Column(String(200), default="")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_cst)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip = Column(String(45), nullable=False)
    hostname = Column(String(255), default="")
    device_type = Column(String(50), nullable=False)
    username = Column(String(255), nullable=False)
    password = Column(String(500), nullable=False)
    port = Column(Integer, default=22)
    status = Column(String(20), default="unknown")
    created_at = Column(DateTime, default=now_cst)
    updated_at = Column(DateTime, default=now_cst, onupdate=now_cst)

    runs = relationship("InspectionRun", back_populates="device", cascade="all, delete-orphan")
    alerts = relationship("AlertRule", back_populates="device", cascade="all, delete-orphan")


class InspectionRun(Base):
    __tablename__ = "inspection_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    timestamp = Column(DateTime, default=now_cst)
    cpu = Column(String(20), default="N/A")
    memory = Column(String(20), default="N/A")
    uptime = Column(String(100), default="N/A")
    hostname = Column(String(255), default="N/A")
    status = Column(String(20), default="unknown")
    error = Column(Text)
    raw_data = Column(Text)
    config_backup = Column(String(255))

    device = relationship("Device", back_populates="runs")


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    metric = Column(String(20), nullable=False)
    operator = Column(String(5), default=">")
    threshold = Column(Float, nullable=False)
    enabled = Column(Boolean, default=True)

    device = relationship("Device", back_populates="alerts")


class InspectionSchedule(Base):
    __tablename__ = "inspection_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    schedule_type = Column(String(20), nullable=False)  # once / hourly / daily / monthly
    schedule_config = Column(JSON, nullable=False)       # {"time":"06:00"} / {"date":"2026-06-15","time":"14:30"} / {"interval_hours":4} / {"day":15,"time":"08:00"}
    device_ids = Column(JSON, default=[])                # empty = all devices
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_cst)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)

