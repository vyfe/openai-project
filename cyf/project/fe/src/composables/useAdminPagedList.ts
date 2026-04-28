import { ref } from 'vue'

export interface AdminPagination {
  page: number
  page_size: number
  total: number
  pages: number
}

type ListResponse<T> = {
  success: boolean
  data?: {
    items?: T[]
    pagination?: AdminPagination
  }
}

type Fetcher<T, P extends Record<string, any>> = (params: P) => Promise<ListResponse<T>>

export function useAdminPagedList<T, P extends Record<string, any> = Record<string, any>>(
  fetcher: Fetcher<T, P>,
  extraParams?: () => Partial<P>
) {
  const items = ref<T[]>([])
  const loading = ref(false)
  const keyword = ref('')
  const pagination = ref<AdminPagination>({
    page: 1,
    page_size: 20,
    total: 0,
    pages: 1
  })

  const fetchList = async () => {
    loading.value = true
    try {
      const params = {
        page: pagination.value.page,
        page_size: pagination.value.page_size,
        keyword: keyword.value || undefined,
        ...(extraParams ? extraParams() : {})
      } as P
      const response = await fetcher(params)
      if (response.success) {
        items.value = response.data?.items || []
        if (response.data?.pagination) {
          pagination.value = response.data.pagination
        }
      }
    } finally {
      loading.value = false
    }
  }

  const search = () => {
    pagination.value.page = 1
    return fetchList()
  }

  const changePage = (page: number) => {
    pagination.value.page = page
    return fetchList()
  }

  const changePageSize = (size: number) => {
    pagination.value.page_size = size
    pagination.value.page = 1
    return fetchList()
  }

  return {
    items,
    loading,
    keyword,
    pagination,
    fetchList,
    search,
    changePage,
    changePageSize
  }
}
