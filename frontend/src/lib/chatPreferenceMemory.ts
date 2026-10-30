const negativePreference = /tidak suka|nggak suka|enggak suka|gak suka|gasuka|ga suka|kurang suka|tidak doyan|nggak doyan|enggak doyan|gak doyan|hindari|jangan/i

function keyFor(customerId: string) {
  return `dova_chat_preferences:${customerId}`
}

/** Keep explicit dislike statements in this tab so they survive route changes. */
export function rememberChatPreference(customerId: string, message: string): string[] {
  let history: string[] = []
  const key = keyFor(customerId)
  try {
    const raw = sessionStorage.getItem(key)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    if (Array.isArray(parsed)) history = parsed.filter((item): item is string => typeof item === 'string')
  } catch {
    history = []
  }

  if (negativePreference.test(message)) {
    history = [...history.filter((item) => item !== message), message].slice(-10)
    try {
      sessionStorage.setItem(key, JSON.stringify(history))
    } catch {
      // Chat continues with the current message if session storage is unavailable.
    }
  }
  return history
}

export function clearChatPreferences(customerId: string) {
  try {
    sessionStorage.removeItem(keyFor(customerId))
  } catch {
    // Ignore unavailable browser storage.
  }
}
