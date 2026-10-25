import { ImagePlus, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../lib/api'
import { reloadLogos, useLogoUrl, type LogoKind } from '../lib/logos'
import { useErrorText } from '../lib/useErrorText'
import { Button, ErrorText } from './ui'

/** Upload an own logo where no icon set has one (Tangem, SafeTrade, …), or remove it. */
export function LogoUpload({ kind, id }: { kind: LogoKind; id: string | number }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const input = useRef<HTMLInputElement>(null)
  const own = useLogoUrl(kind, id)
  const [error, setError] = useState<unknown>(null)
  const upload = (file: File | undefined) => {
    if (!file) return
    api.uploadLogo(kind, id, file).then(() => { setError(null); reloadLogos() }, setError)
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <input ref={input} type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" hidden
        onChange={(e) => { upload(e.target.files?.[0]); e.target.value = '' }} />
      <Button variant="ghost" onClick={() => input.current?.click()}>
        <ImagePlus size={15} aria-hidden="true" />{own ? t('logos.replace') : t('logos.upload')}
      </Button>
      {own && (
        <Button variant="ghost" onClick={() => api.removeLogo(kind, id).then(reloadLogos, setError)}>
          <X size={15} aria-hidden="true" />{t('logos.remove')}
        </Button>
      )}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </span>
  )
}
