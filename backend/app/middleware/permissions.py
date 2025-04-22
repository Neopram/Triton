from enum import Enum
from typing import List, Optional, Callable, Dict, Any
from fastapi import Depends, HTTPException, status
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.core.logging import auth_logger


class ResourceType(str, Enum):
    VESSEL = "vessel"
    VOYAGE = "voyage"
    MARKET = "market"
    FINANCE = "finance"
    MESSAGE = "message"
    USER = "user"
    INSIGHT = "insight"
    ADMIN = "admin"


class Operation(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    EXECUTE = "execute"


# Permission matrix - which roles can perform which operations on which resources
ROLE_PERMISSIONS: Dict[UserRole, Dict[ResourceType, List[Operation]]] = {
    UserRole.admin: {
        # Admins can do everything
        resource_type: list(Operation)
        for resource_type in ResourceType
    },
    UserRole.fleet_manager: {
        ResourceType.VESSEL: [Operation.CREATE, Operation.READ, Operation.UPDATE, Operation.DELETE, Operation.LIST],
        ResourceType.VOYAGE: [Operation.CREATE, Operation.READ, Operation.UPDATE, Operation.DELETE, Operation.LIST],
        ResourceType.MARKET: [Operation.CREATE, Operation.READ, Operation.UPDATE, Operation.DELETE, Operation.LIST],
        ResourceType.FINANCE: [Operation.READ, Operation.LIST],
        ResourceType.MESSAGE: [Operation.CREATE, Operation.READ, Operation.DELETE, Operation.LIST],
        ResourceType.USER: [Operation.READ, Operation.LIST],
        ResourceType.INSIGHT: [Operation.CREATE, Operation.READ, Operation.LIST],
        ResourceType.ADMIN: []  # No admin access
    },
    UserRole.analyst: {
        ResourceType.VESSEL: [Operation.READ, Operation.LIST],
        ResourceType.VOYAGE: [Operation.READ, Operation.LIST],
        ResourceType.MARKET: [Operation.READ, Operation.LIST, Operation.CREATE],
        ResourceType.FINANCE: [Operation.READ, Operation.LIST],
        ResourceType.MESSAGE: [Operation.CREATE, Operation.READ, Operation.DELETE, Operation.LIST],
        ResourceType.USER: [Operation.READ, Operation.LIST],
        ResourceType.INSIGHT: [Operation.CREATE, Operation.READ, Operation.LIST],
        ResourceType.ADMIN: []  # No admin access
    },
    UserRole.viewer: {
        ResourceType.VESSEL: [Operation.READ, Operation.LIST],
        ResourceType.VOYAGE: [Operation.READ, Operation.LIST],
        ResourceType.MARKET: [Operation.READ, Operation.LIST],
        ResourceType.FINANCE: [Operation.READ, Operation.LIST],
        ResourceType.MESSAGE: [Operation.CREATE, Operation.READ, Operation.LIST],
        ResourceType.USER: [Operation.READ, Operation.LIST],
        ResourceType.INSIGHT: [Operation.READ, Operation.LIST],
        ResourceType.ADMIN: []  # No admin access
    }
}


def verify_permission(
    resource_type: ResourceType,
    operation: Operation,
    owner_check: Optional[Callable[[User, Any], bool]] = None
):
    """
    Dependency for checking permissions on a resource
    
    Args:
        resource_type: Type of resource being accessed
        operation: Operation being performed
        owner_check: Optional function to check if user owns the resource
        
    Returns:
        Dependency function for FastAPI
    """
    async def check_permission(
        current_user: User = Depends(get_current_user),
        resource_id: Optional[int] = None
    ):
        if current_user.role not in ROLE_PERMISSIONS:
            auth_logger.structured(
                "error",
                f"Permission denied: Unknown role {current_user.role}",
                {
                    "user_id": current_user.id,
                    "resource_type": resource_type,
                    "operation": operation,
                    "resource_id": resource_id
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        # Check role-based permissions
        allowed_operations = ROLE_PERMISSIONS.get(current_user.role, {}).get(resource_type, [])
        if operation not in allowed_operations:
            auth_logger.structured(
                "warning",
                f"Permission denied: {current_user.role} cannot {operation} on {resource_type}",
                {
                    "user_id": current_user.id,
                    "role": current_user.role,
                    "resource_type": resource_type,
                    "operation": operation,
                    "resource_id": resource_id
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        # Return the current user for use in the route
        return current_user
    
    return check_permission


# Common permission dependencies
def admin_only(current_user: User = Depends(get_current_user)):
    """Ensure only admins can access the route"""
    if current_user.role != UserRole.admin:
        auth_logger.structured(
            "warning",
            f"Admin access denied for {current_user.role}",
            {"user_id": current_user.id, "role": current_user.role}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def fleet_manager_or_admin(current_user: User = Depends(get_current_user)):
    """Ensure only fleet managers or admins can access the route"""
    if current_user.role not in [UserRole.admin, UserRole.fleet_manager]:
        auth_logger.structured(
            "warning",
            f"Fleet manager access denied for {current_user.role}",
            {"user_id": current_user.id, "role": current_user.role}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fleet manager or admin access required"
        )
    return current_user


def can_manage_market_data(current_user: User = Depends(get_current_user)):
    """Check if user can manage market data"""
    if current_user.role not in [UserRole.admin, UserRole.fleet_manager, UserRole.analyst]:
        auth_logger.structured(
            "warning",
            f"Market data management denied for {current_user.role}",
            {"user_id": current_user.id, "role": current_user.role}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage market data"
        )
    return current_user