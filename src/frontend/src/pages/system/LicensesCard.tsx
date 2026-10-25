import { useTranslation } from 'react-i18next'
import { Card } from '../../components/ui'

// what owncryptofolio uses of others (THIRD-PARTY-NOTICES.md); names and licences, no translation
const WORKS: [string, string, string][] = [
  ['web3icons', 'MIT', 'https://web3icons.io'],
  ['cryptocurrency-icons', 'CC0 1.0', 'http://cryptoicons.co'],
  ['IBM Plex Sans / Mono', 'OFL 1.1', 'https://github.com/IBM/plex'],
  ['Onest', 'OFL 1.1', 'https://github.com/simpals/onest'],
  ['Sora', 'OFL 1.1', 'https://github.com/sora-xor/sora-font'],
  ['Lucide', 'ISC', 'https://lucide.dev'],
  ['React, React Router, i18next', 'MIT', 'https://react.dev'],
  ['Apache ECharts', 'Apache 2.0', 'https://echarts.apache.org'],
  ['FastAPI, SQLAlchemy, Alembic, ccxt, openpyxl, mcp', 'MIT', 'https://fastapi.tiangolo.com'],
  ['Uvicorn', 'BSD 3-Clause', 'https://www.uvicorn.org'],
  ['cryptography', 'Apache 2.0 / BSD', 'https://cryptography.io'],
  ['psycopg, fpdf2', 'LGPL 3.0', 'https://www.psycopg.org'],
]

/** Licences of the works used, and whose marks the logos are (Vanixxx, 2026-10-23). */
export function LicensesCard() {
  const { t } = useTranslation()
  return (
    <Card fold="system-open-licenses" title={t('system.licenses.title')} className="md:col-span-2">
      <ul className="m-0 grid list-none gap-1 p-0 text-sm sm:grid-cols-2">
        {WORKS.map(([name, licence, url]) => (
          <li key={name} className="flex min-w-0 items-baseline justify-between gap-3">
            <a href={url} target="_blank" rel="noreferrer" className="truncate text-fg no-underline hover:text-accent">{name}</a>
            <span className="shrink-0 text-xs text-muted">{licence}</span>
          </li>
        ))}
      </ul>
      <p className="m-0 text-xs leading-relaxed text-muted">{t('system.licenses.marks')}</p>
    </Card>
  )
}
