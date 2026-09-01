
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
            env_file='.env',
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore"
    )

    # LLM
    openai_api_key:str = Field(...)
    openai_embedding_model:str = Field(default="text-embedding-3-small")
    openai_chat_model:str = Field(default="gpt-4o-mini")

    # Tracing
    langsmith_api_key:str = Field(..., description="LangSmith API key for agent tracing")
    langsmith_project:str = Field(default='clinical_trial_intelligence', description='LangSmith project name')
    langsmith_tracing_v2:bool = Field(default=True, description="Enable langsmith tracing for all agent runs")

    # Deployment
    gcp_project_id:str = Field(...)
    gcp_region:str = Field(default='us-central1')
    gcs_bucket_name:str = Field(...)
    
    # Database
    db_host:str = Field(...)
    db_port:int = Field(default=5432, description="PostgreSQL port")
    db_name:str = Field(default="clinical_trial_db")
    db_user:str = Field(...)
    db_password:str = Field(...)

    # DataSource
    clinical_trials_base_url:str = Field(default="https://clinicaltrials.gov/api/v2")
    clinical_trials_page_size:int = Field(default=100, description="Number of studies to fetch per API page")
    pubmed_base_url:str = Field(
        default="https://eutils.ncbi.nlm.nih.gov/entrez/eutils", 
        description="Pubmed eutils API base url"
    )

    # Server
    api_host:str = Field(default="0.0.0.0", description="Host address")
    api_port:int = Field(default=8000)
    api_env:str = Field(default='development')

    @property
    def database_url(self)-> str:
        """
        Build async DB connection string

        returns:
        str: full connection url ready for asyncpg.create_pool() \n
        example: postgresql+asyncpg://user:password@host:port/db_name
        """
        return (
            f"postgresql+asyncpg://"
            f"{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}"
            f"/{self.db_name}"
        )

    @property
    def is_production(self)->bool:
        """returns True if app is running in production"""
        return self.api_env.lower() == "production"


settings = Settings()