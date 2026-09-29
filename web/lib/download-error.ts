/** Read the API error envelope even when a proxy drops the response media type. */
export async function readDownloadError(data: unknown): Promise<string | undefined> {
  let payload = data;
  if (data instanceof Blob) {
    // Real XLSX downloads are ZIP binaries. Inspect only a small prefix before
    // decoding an error body so large successful files are not read as text.
    if (!(await data.slice(0, 128).text()).trimStart().startsWith('{')) return undefined;
    payload = await data.text();
  }
  if (typeof payload === 'string') {
    try {
      payload = JSON.parse(payload);
    } catch {
      return undefined;
    }
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return undefined;
  const message = (payload as Record<string, unknown>).err_msg;
  return typeof message === 'string' && message.length > 0 ? message : undefined;
}
