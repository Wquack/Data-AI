from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from models.user_token import UserToken
from utils.db import SessionLocal
import logging


logger = logging.getLogger(__name__)


def save_tokens(user_id, token_data: dict):
    """
    Save tokens for multiple services (e.g., google, slack, zoom).
    Each service will have its own row.
    """
    session: Session = SessionLocal()

    try:
        for service, tokens in token_data.items():
            existing = session.query(UserToken).filter_by(user_id=user_id, service=service).first()
            expires_at = None

            # Parse expires_at if available
            if "expires_in" in tokens:
                expires_at = datetime.utcnow() + timedelta(seconds=int(tokens["expires_in"]))
            elif "expires_at" in tokens:
                if "expires_at" in tokens:
                    try:
                        expires_at = datetime.fromisoformat(tokens["expires_at"])
                    except (ValueError, TypeError):
                        expires_at = None

            if existing:
                existing.access_token = tokens["access_token"]
                existing.refresh_token = tokens.get("refresh_token")
                existing.expires_at = expires_at   # type: ignore[attr-defined]
            else:
                new_token = UserToken(
                    user_id=user_id,
                    service=service,
                    access_token=tokens["access_token"],
                    refresh_token=tokens.get("refresh_token"),
                    expires_at=expires_at
                )
                session.add(new_token)

        session.commit()
        logger.info(f"Tokens saved for {user_id}")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error saving tokens for {user_id}: {str(e)}")
        raise
    finally:
        session.close()


def remove_tokens(user_id):
    """
    Remove all tokens for a given user_id.
    """
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


def load_tokens(user_id: str) -> dict:
    """
    Load all tokens for the user. Returns a dict by service.
    """
    session: Session = SessionLocal()
    tokens_by_service = {}
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
        logger.error(f"Error loading tokens for {user_id}: {str(e)}")
        return {}
    finally:
        session.close()
