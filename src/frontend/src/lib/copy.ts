/** Copy text, also over plain http in the home network: the Clipboard API only exists on
 * https or localhost (Vanixxx, 2026-10-19: the copy button did nothing at http://<IP>:8000). */
export async function copyText(text: string): Promise<boolean> {
  if (window.isSecureContext && navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch { /* fall through to the old way */ }
  }
  const area = Object.assign(document.createElement('textarea'), { value: text, readOnly: true })
  area.style.position = 'fixed'
  area.style.opacity = '0'
  document.body.appendChild(area)
  area.select()
  try {
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    area.remove()
  }
}
