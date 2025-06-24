import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Set, List, Union # Import Union for type hinting
from typing import Annotated
from pydantic import Field, field_validator, BeforeValidator # Import Field and field_validator for Pydantic v2+
import logging

# --- Explicit Logger Setup for Debugging in config.py ---
# This ensures that messages from THIS module are always printed during debugging,
# even if the main application's logging setup is different or less verbose.
logger = logging.getLogger(__name__) # Get a logger instance for this module
if not logger.handlers: # Only add handler if it's not already configured (prevents duplicate output)
    handler = logging.StreamHandler() # Output to console
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO) # Set this logger's level to INFO
# --------------------------------------------------------


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        enable_decoding=False,  # Disable automatic decoding of environment variables
    )

    # --- Blogger API Configuration ---
    BLOGGER_API_KEY: str

    # --- MCP Server Configuration ---
    MCP_SERVER_NAME: str = "QueryBloggerMCPServer"
    MCP_SERVER_VERSION: str = "0.1.0"
    MCP_SERVER_DESCRIPTION: str = "Provides read-only tools to query public Blogger content from specific, allowed domains."

    # --- Domain Filtering for Blogger ---
    @field_validator('ALLOWED_DOMAINS', mode='before') # This method runs before the main validation
    @classmethod
    def _parse_allowed_domains(cls, v: Union[str, Set[str]]) -> Set[str]:
        """
        Parses a comma-separated string of domains into a set of strings.
        This validator runs *before* Pydantic's main validation for the field.
        """
        logger.debug(f"Validator: Raw value received for ALLOWED_DOMAINS: '{v}' (type: {type(v)})")
        if isinstance(v, set):
            logger.debug("Validator: Value is already a set.")
            return v # If it's already a set (e.g., from default_factory), return it as is.
        if not v: # Handles empty string input
            logger.debug("Validator: Value is empty string, returning empty set.")
            return set()
        # Split the string by commas, strip whitespace from each part, and convert to a set
        try:
            parsed_set = {domain.strip() for domain in v.split(',')}
            logger.debug(f"Validator: Successfully parsed into: {parsed_set}")
            return parsed_set
        except Exception as e:
            logger.error(f"Validator: Error during parsing ALLOWED_DOMAINS '{v}': {e}")
            raise # Re-raise to let Pydantic handle it

    # We use Field(default_factory=set) to ensure an empty set is the default
    # if the environment variable is not provided, or is empty.
    # ALLOWED_DOMAINS: Set[str] = Field(..., default_factory=set, description="Set of allowed domains for querying Blogger content.")
    # ALLOWED_DOMAINS: Annotated[Set[str], BeforeValidator(_parse_allowed_domains)] = set()
    ALLOWED_DOMAINS: Set[str] = Field()

    # --- Server Host and Port (for Uvicorn) ---
    UVICORN_HOST: str = "0.0.0.0"
    UVICORN_PORT: int = 8000

# Try to load settings and log success/failure at the module level
try:
    logger.info("Attempting to load settings from config.py...")
    settings = Settings()
    logger.debug(f"Settings = {settings.model_dump()}")
    logger.info("Settings loaded successfully from config.py.")
except Exception as e:
    # logger.info(f"ALLOWED_DOMAINS = {ALLOWED_DOMAINS}")
    logger.error(f"Failed to load settings in config.py: {e}")
    raise
