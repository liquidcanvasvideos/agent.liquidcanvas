import { useState, useEffect, useCallback } from 'react'

export interface PaginatedResponse<T> {
  data: T[]
  page: number
  limit: number
  total: number
  totalPages: number
}

export interface UsePaginatedFetchOptions {
  fetchFn: (page: number, limit: number) => Promise<PaginatedResponse<any>>
  initialPage?: number
  limit?: number
  autoLoad?: boolean
}

export interface UsePaginatedFetchReturn<T> {
  page: number
  setPage: (page: number) => void
  data: T[]
  totalPages: number
  total: number
  loading: boolean
  error: string | null
  limit: number
  refresh: () => Promise<void>
  goToNext: () => void
  goToPrev: () => void
  canGoNext: boolean
  canGoPrev: boolean
}

export function usePaginatedFetch<T = any>(
  options: UsePaginatedFetchOptions
): UsePaginatedFetchReturn<T> {
  const {
    fetchFn,
    initialPage = 1,
    limit = 10,
    autoLoad = true,
  } = options

  const [page, setPage] = useState(initialPage)
  const [data, setData] = useState<T[]>([])
  const [totalPages, setTotalPages] = useState(0)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetchFn(page, limit)
      
      // Handle both standardized format and backward compatibility
      // Safely extract array from response, handling nested formats
      let items: T[] = []
      if (Array.isArray(response.data)) {
        items = response.data
      } else if (response.data && typeof response.data === 'object' && response.data !== null) {
        // Handle nested data.data or data.prospects formats
        const dataObj = response.data as Record<string, unknown>
        if ('data' in dataObj && Array.isArray(dataObj.data)) {
          items = dataObj.data as T[]
        } else if ('prospects' in dataObj && Array.isArray(dataObj.prospects)) {
          items = dataObj.prospects as T[]
        } else if ('items' in dataObj && Array.isArray(dataObj.items)) {
          items = dataObj.items as T[]
        }
      } else {
        // Fallback to other response formats
        const responseAny = response as unknown as Record<string, unknown>
        if (Array.isArray(responseAny.prospects)) {
          items = responseAny.prospects as T[]
        } else if (Array.isArray(responseAny.items)) {
          items = responseAny.items as T[]
        }
      }
      
      const totalPages = response.totalPages || (response as unknown as Record<string, unknown>).total_pages as number || 0
      const total = response.total || 0
      
      // Ensure items is always an array
      setData(Array.isArray(items) ? items : [])
      setTotalPages(totalPages)
      setTotal(total)
    } catch (err: any) {
      setError(err.message || 'Failed to load data')
      setData([])
      setTotalPages(0)
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [fetchFn, page, limit])

  useEffect(() => {
    if (autoLoad) {
      loadData()
    }
  }, [loadData, autoLoad])

  const goToNext = useCallback(() => {
    setPage((prev) => Math.min(prev + 1, totalPages))
  }, [totalPages])

  const goToPrev = useCallback(() => {
    setPage((prev) => Math.max(prev - 1, 1))
  }, [])

  const canGoNext = page < totalPages
  const canGoPrev = page > 1

  return {
    page,
    setPage,
    data,
    totalPages,
    total,
    loading,
    error,
    limit,
    refresh: loadData,
    goToNext,
    goToPrev,
    canGoNext,
    canGoPrev,
  }
}




