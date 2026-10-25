# Third-party notices

owncryptofolio uses the following works of others. Each keeps its own licence; the full
licence texts ship with the packages (`node_modules/<package>/LICENSE`, Python
`site-packages/<package>-*.dist-info`).

## Icons and fonts (shipped with the web interface)

| Work | Used for | Licence | Source |
|---|---|---|---|
| web3icons (`@web3icons/core`) | coin, network, exchange and wallet symbols | MIT | https://web3icons.io |
| cryptocurrency-icons | coin symbols missing in web3icons | CC0 1.0 (public domain) | http://cryptoicons.co |
| IBM Plex Sans, IBM Plex Mono | text and numbers | SIL Open Font License 1.1 | https://github.com/IBM/plex (via Fontsource) |
| Onest | text in some styles | SIL Open Font License 1.1 | https://github.com/simpals/onest (via Fontsource) |
| Sora | text in some styles | SIL Open Font License 1.1 | https://github.com/sora-xor/sora-font (via Fontsource) |
| Lucide | interface icons | ISC | https://lucide.dev |

Website icons of exchanges not in web3icons are not shipped: each installation fetches them
from the exchange's own website when first shown and keeps them in its data folder.

Names and logos of exchanges, wallets, networks and coins are trademarks of their owners.
They are shown only to name the service a record comes from; owncryptofolio is not
affiliated with or endorsed by any of them.

## Libraries

Web interface: React, React DOM, React Router, i18next, react-i18next (MIT), Apache ECharts
(Apache 2.0).

Server: FastAPI, SQLAlchemy, Alembic, pydantic-settings, ccxt, openpyxl, mcp (MIT), Uvicorn
(BSD 3-Clause), cryptography (Apache 2.0 or BSD 3-Clause), python-multipart (Apache 2.0),
psycopg and fpdf2 (LGPL 3.0, used unchanged as libraries).

## Data services

Prices and on-chain data come from public APIs (exchanges, block explorers, Yahoo Finance);
their terms apply to their data. owncryptofolio stores what it fetches only in the user's own
database.
