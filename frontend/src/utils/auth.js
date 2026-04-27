export const ALLOWED_USER_ID = 'helloworld666'

export function hasValidLocalAuth() {
  const token = localStorage.getItem('chat_token')
  const userId = localStorage.getItem('chat_user_id')
  return Boolean(token) && userId === ALLOWED_USER_ID
}

export function clearLocalAuth() {
  localStorage.removeItem('chat_token')
  localStorage.removeItem('chat_user_id')
}
