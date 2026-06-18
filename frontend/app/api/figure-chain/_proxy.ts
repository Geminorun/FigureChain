export function buildForwardPath(
  path: string,
  source: URLSearchParams,
  allowedKeys: string[],
): string {
  const query = new URLSearchParams();
  for (const key of allowedKeys) {
    const value = source.get(key);
    if (value !== null) {
      query.set(key, value);
    }
  }
  const queryString = query.toString();
  return queryString ? `${path}?${queryString}` : path;
}
