export async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  })

  if (!response.ok) {
    let message = '请求失败'
    try {
      const data = await response.json()
      message = data.detail || data.message || message
    } catch {
      // ignore
    }
    throw new Error(message)
  }

  return response.json()
}

export async function uploadApi(path, formData) {
  const response = await fetch(`/api${path}`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    let message = '请求失败'
    try {
      const data = await response.json()
      message = data.detail || data.message || message
    } catch {
      // ignore
    }
    throw new Error(message)
  }

  return response.json()
}
