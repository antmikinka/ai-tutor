"""
System and administrative API endpoints
"""

import json
import logging
import platform
import psutil
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models for request/response
class SystemInfoResponse(BaseModel):
    hostname: str
    platform: str
    platform_version: str
    architecture: str
    processor: str
    python_version: str
    total_memory: int
    available_memory: int
    cpu_count: int
    cpu_usage: float
    disk_usage: Dict[str, int]
    network_info: Dict[str, Any]
    timestamp: str

class ServiceStatusResponse(BaseModel):
    services: Dict[str, Dict[str, Any]]
    overall_status: str
    timestamp: str

class ConfigResponse(BaseModel):
    config: Dict[str, Any]
    timestamp: str

class LogResponse(BaseModel):
    logs: List[Dict[str, Any]]
    total_count: int
    timestamp: str

class HealthCheckResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, str]
    metrics: Dict[str, Any]

# Settings
settings = get_settings()

@router.get("/system-info", response_model=SystemInfoResponse)
async def get_system_info():
    """
    Get detailed system information
    """
    try:
        logger.info("Getting system information")

        # Get system information
        system_info = {
            "hostname": platform.node(),
            "platform": platform.system(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version,
            "total_memory": psutil.virtual_memory().total,
            "available_memory": psutil.virtual_memory().available,
            "cpu_count": psutil.cpu_count(),
            "cpu_usage": psutil.cpu_percent(interval=1),
            "disk_usage": {
                "total": psutil.disk_usage('/').total,
                "used": psutil.disk_usage('/').used,
                "free": psutil.disk_usage('/').free
            },
            "network_info": {
                "interfaces": psutil.net_if_addrs(),
                "io_counters": psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {}
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        return SystemInfoResponse(**system_info)

    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system info: {str(e)}")

@router.get("/service-status", response_model=ServiceStatusResponse)
async def get_service_status():
    """
    Get status of all backend services
    """
    try:
        logger.info("Getting service status")

        # This is a placeholder implementation
        # In production, you would check actual service statuses
        services = {
            "ai_service": {
                "status": "running",
                "memory_usage": "512MB",
                "cpu_usage": "15%",
                "last_check": datetime.utcnow().isoformat()
            },
            "audio_service": {
                "status": "running",
                "memory_usage": "256MB",
                "cpu_usage": "5%",
                "last_check": datetime.utcnow().isoformat()
            },
            "drawing_service": {
                "status": "running",
                "memory_usage": "128MB",
                "cpu_usage": "3%",
                "last_check": datetime.utcnow().isoformat()
            },
            "model_service": {
                "status": "running",
                "memory_usage": "2048MB",
                "cpu_usage": "25%",
                "last_check": datetime.utcnow().isoformat()
            },
            "database": {
                "status": "connected",
                "connection_pool_size": 10,
                "active_connections": 2,
                "last_check": datetime.utcnow().isoformat()
            }
        }

        # Determine overall status
        all_running = all(service["status"] == "running" for service in services.values())
        overall_status = "healthy" if all_running else "degraded"

        return ServiceStatusResponse(
            services=services,
            overall_status=overall_status,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get service status: {str(e)}")

@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """
    Get current configuration (sensitive information filtered)
    """
    try:
        logger.info("Getting configuration")

        # Get safe configuration (filter sensitive information)
        safe_config = {
            "app_name": settings.app_name,
            "version": settings.version,
            "debug": settings.debug,
            "environment": settings.environment,
            "host": settings.host,
            "port": settings.port,
            "ai_model_name": settings.ai_model_name,
            "ai_temperature": settings.ai_temperature,
            "ai_max_tokens": settings.ai_max_tokens,
            "ai_use_gpu": settings.ai_use_gpu,
            "whisper_model": settings.whisper_model,
            "tts_model": settings.tts_model,
            "log_level": settings.log_level,
            "max_upload_size": settings.max_upload_size,
            "max_concurrent_requests": settings.max_concurrent_requests,
            "websocket_ping_interval": settings.websocket_ping_interval,
        }

        return ConfigResponse(
            config=safe_config,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")

@router.get("/logs", response_model=LogResponse)
async def get_logs(
    limit: int = 100,
    offset: int = 0,
    level: Optional[str] = None,
    service: Optional[str] = None
):
    """
    Get application logs
    """
    try:
        logger.info("Getting application logs")

        # This is a placeholder implementation
        # In production, you would read from actual log files or database
        logs = []

        # Simulate some log entries
        for i in range(min(limit, 50)):
            log_entry = {
                "timestamp": (datetime.utcnow().timestamp() - i * 60) * 1000,  # milliseconds
                "level": ["INFO", "WARNING", "ERROR"][i % 3],
                "service": ["ai_service", "audio_service", "drawing_service"][i % 3],
                "message": f"Sample log message {i}",
                "source": "system_api.py"
            }
            logs.append(log_entry)

        # Filter by level if specified
        if level:
            logs = [log for log in logs if log["level"] == level]

        # Filter by service if specified
        if service:
            logs = [log for log in logs if log["service"] == service]

        # Apply pagination
        total_count = len(logs)
        logs = logs[offset:offset + limit]

        return LogResponse(
            logs=logs,
            total_count=total_count,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")

@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Comprehensive health check for monitoring
    """
    try:
        logger.info("Performing health check")

        # Check system resources
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Service health (placeholder)
        services = {
            "ai_service": "healthy",
            "audio_service": "healthy",
            "drawing_service": "healthy",
            "model_service": "healthy",
            "database": "healthy",
            "websocket": "healthy"
        }

        # Determine overall health
        all_healthy = all(status == "healthy" for status in services.values())
        overall_status = "healthy" if all_healthy else "unhealthy"

        # System metrics
        metrics = {
            "memory_usage_percent": memory.percent,
            "disk_usage_percent": (disk.used / disk.total) * 100,
            "cpu_usage_percent": psutil.cpu_percent(interval=1),
            "uptime_seconds": datetime.utcnow().timestamp() - psutil.boot_time(),
            "active_connections": 0,  # Would get actual count in production
            "request_count": 0,  # Would track actual requests in production
        }

        return HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            services=services,
            metrics=metrics
        )

    except Exception as e:
        logger.error(f"Error during health check: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.post("/restart-service")
async def restart_service(service_name: str):
    """
    Restart a specific service (admin only)
    """
    try:
        logger.info(f"Restarting service: {service_name}")

        # This is a placeholder implementation
        # In production, you would implement actual service restart logic

        valid_services = ["ai_service", "audio_service", "drawing_service", "model_service"]
        if service_name not in valid_services:
            raise HTTPException(status_code=400, detail=f"Invalid service name: {service_name}")

        # Simulate service restart
        await asyncio.sleep(1)  # Simulate restart time

        return {
            "message": f"Service {service_name} restarted successfully",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error restarting service {service_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restart service: {str(e)}")

@router.get("/metrics")
async def get_metrics():
    """
    Get system and application metrics for monitoring
    """
    try:
        logger.info("Getting metrics")

        # System metrics
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()

        metrics = {
            "system": {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": memory.percent,
                "memory_used": memory.used,
                "memory_total": memory.total,
                "disk_percent": (disk.used / disk.total) * 100,
                "disk_used": disk.used,
                "disk_total": disk.total,
                "network_bytes_sent": network.bytes_sent if network else 0,
                "network_bytes_recv": network.bytes_recv if network else 0,
            },
            "application": {
                "uptime_seconds": datetime.utcnow().timestamp() - psutil.boot_time(),
                "active_requests": 0,  # Would track actual requests
                "total_requests": 0,  # Would track total requests
                "error_rate": 0.0,  # Would calculate actual error rate
                "response_time_avg": 0.0,  # Would track actual response times
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        return metrics

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

@router.post("/clear-cache")
async def clear_cache():
    """
    Clear application cache
    """
    try:
        logger.info("Clearing application cache")

        # This is a placeholder implementation
        # In production, you would clear actual cache directories

        import shutil
        import os

        cache_dirs = [
            settings.model_cache_dir,
            Path("temp"),
            Path("cache")
        ]

        cleared_dirs = []
        for cache_dir in cache_dirs:
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                cache_dir.mkdir(parents=True, exist_ok=True)
                cleared_dirs.append(str(cache_dir))

        return {
            "message": "Cache cleared successfully",
            "cleared_directories": cleared_dirs,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

# Import asyncio for the restart service endpoint
import asyncio
from pathlib import Path