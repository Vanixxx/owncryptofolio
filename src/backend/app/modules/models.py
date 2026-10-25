"""Imports every module's models so Alembic sees all tables. Add new modules here."""

from app.modules.auth.models import AuthCredential  # noqa: F401
from app.modules.backup.models import BackupRun  # noqa: F401
from app.modules.balances.models import BalanceSnapshot  # noqa: F401
from app.modules.imports.models import ImportMapping  # noqa: F401
from app.modules.jobs.models import Job  # noqa: F401
from app.modules.logos.models import CustomLogo  # noqa: F401
from app.modules.mcp.models import McpChange, McpToken  # noqa: F401
from app.modules.merged.models import (  # noqa: F401
    NotDustMark,
    OpenSendMark,
    SpamMark,
    TransferDecision,
    TransferExtra,
    TxNote,
)
from app.modules.portfolio.models import PortfolioTick  # noqa: F401
from app.modules.prices.models import (  # noqa: F401
    AssetAlias,
    FxDaily,
    PriceAsset,
    PriceDaily,
    PriceFine,
    PriceGap,
    PriceLatest,
    PriceMappingChange,
    PriceSource,
)
from app.modules.raw.models import ImportRun, RawRetraction, RawTransaction  # noqa: F401
from app.modules.settings.models import Setting  # noqa: F401
from app.modules.sources.models import ServiceKey, Source, SourceCredential, Wallet  # noqa: F401
from app.modules.tax.models import TaxReport  # noqa: F401
