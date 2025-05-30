from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from models.user_token import UserToken
from utils.db import SessionLocal
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def save_tokens(user_id: str, token_data: Dict[str, Dict[str, Any]]) -> None:
    """
    Save tokens for multiple services (e.g., google, slack, zoom).
    Each service will have its own row.

    Args:
        user_id: The ID of the user.
        token_data: A dictionary mapping service names to their token data.

    Raises:
        ValueError: If user_id is invalid or access_token is missing or invalid.
        SQLAlchemyError: If a database error occurs.
    """
    # Validate user_id
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id must be a non-empty string")

    session: Session = SessionLocal()

    try:
        for service, tokens in token_data.items():
            logger.debug(f"Saving tokens for user {user_id}, service {service}")
            
            # Validate access_token
            if "access_token" not in tokens or not isinstance(tokens["access_token"], str) or not tokens["access_token"].strip():
                raise ValueError(f"Invalid or missing access_token for user {user_id}, service {service}")
            
            existing = session.query(UserToken).filter_by(user_id=user_id, service=service).first()
            expires_at = None

            # Parse expires_at if available
            if "expires_in" in tokens:
                expires_at = datetime.utcnow() + timedelta(seconds=int(tokens["expires_in"]))
            elif "expires_at" in tokens:
                expires_at_value = tokens["expires_at"]
                if isinstance(expires_at_value, str):
                    try:
                        expires_at = datetime.fromisoformat(expires_at_value)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid expires_at format for user {user_id}, service {service}: {expires_at_value}")
                        expires_at = None
                else:
                    logger.warning(f"expires_at must be a string for user {user_id}, service {service}: {expires_at_value}")
                    expires_at = None

            if existing:
                # Update existing token
                logger.debug(f"Updating existing token for user {user_id}, service {service}")
                assert existing is not None  # Type assertion for Pylance
                existing.access_token = tokens["access_token"]
                refresh_token = tokens.get("refresh_token")
                if refresh_token is not None and not isinstance(refresh_token, str):
                    logger.warning(f"refresh_token must be a string or None for user {user_id}, service {service}: {refresh_token}")
                    refresh_token = None
                existing.refresh_token = refresh_token
                existing.expires_at = expires_at
            else:
                # Create new token
                logger.debug(f"Creating new token for user {user_id}, service {service}")
                refresh_token = tokens.get("refresh_token")
                if refresh_token is not None and not isinstance(refresh_token, str):
                    logger.warning(f"refresh_token must be a string or None for user {user_id}, service {service}: {refresh_token}")
                    refresh_token = None
                new_token = UserToken(
                    user_id=user_id,
                    service=service,
                    access_token=tokens["access_token"],
                    refresh_token=refresh_token,
                    expires_at=expires_at
                )
                session.add(new_token)

        session.commit()
        logger.info(f"Tokens saved for user {user_id}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error saving tokens for user {user_id}: {str(e)}")
        raise
    finally:
        session.close()

def remove_tokens(user_id: str) -> None:
    """
    Remove all tokens for a given user_id.

    Args:
        user_id: The ID of the user whose tokens should be removed.

    Raises:
        ValueError: If user_id is invalid.
        SQLAlchemyError: If a database error occurs.
    """
    # Validate user_id
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id must be a non-empty string")

    session: Session = SessionLocal()
    try:
        # Delete all tokens for the user
        session.query(UserToken).filter(UserToken.user_id == user_id).delete()
        session.commit()
        logger.info(f"All tokens removed for user_id {user_id}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error removing tokens for user_id {user_id}: {str(e)}")
        raise
    finally:
        session.close()

def load_tokens(user_id: str) -> Dict[str, Dict[str, Any]]:
    """
    Load all tokens for the user. Returns a dict by service.

    Args:
        user_id: The ID of the user whose tokens should be loaded.

    Returns:
        A dictionary mapping services to their token data.
        Returns an empty dictionary if an error occurs.

    Raises:
        ValueError: If user_id is invalid.
        SQLAlchemyError: If a database error occurs.
    """
    # Validate user_id
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id must be a non-empty string")

    session: Session = SessionLocal()
    tokens_by_service: Dict[str, Dict[str, Any]] = {}
    try:
        all_tokens = session.query(UserToken).filter_by(user_id=user_id).all()
        for token in all_tokens:
            tokens_by_service[token.service] = {
                "access_token": token.access_token,
                "refresh_token": token.refresh_token,
                "expires_at": token.expires_at
            }
        return tokens_by_service
    except SQLAlchemyError as e:
        logger.error(f"Error loading tokens for user {user_id}: {str(e)}")
        return {}
    finally:
        session.close()