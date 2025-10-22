# -*- coding: utf-8 -*-
"""Application dependency injector."""
from .sql.database import SessionLocal
import logging

logger = logging.getLogger(__name__)

# Database #########################################################################################
async def get_db():
    """Generates database sessions and closes them when finished."""
    logger.debug("Getting database SessionLocal")
    db = SessionLocal()
    try:
        yield db
        await db.commit()
    except:
        await db.rollback()
        raise
    finally:
        await db.close()
