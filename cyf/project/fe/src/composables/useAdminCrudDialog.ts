import { ref } from 'vue'

export type CrudDialogMode = 'create' | 'edit'

const clonePlain = <T>(value: T): T => JSON.parse(JSON.stringify(value))

export function useAdminCrudDialog<TForm, TRow = TForm>(
  createInitialForm: () => TForm,
  mapRowToForm?: (row: TRow) => TForm
) {
  const dialogVisible = ref(false)
  const dialogMode = ref<CrudDialogMode>('create')
  const formData = ref<TForm>(createInitialForm())

  const openCreateDialog = () => {
    dialogMode.value = 'create'
    formData.value = createInitialForm()
    dialogVisible.value = true
  }

  const openEditDialog = (row: TRow) => {
    dialogMode.value = 'edit'
    formData.value = mapRowToForm ? mapRowToForm(row) : clonePlain(row as unknown as TForm)
    dialogVisible.value = true
  }

  const closeDialog = () => {
    dialogVisible.value = false
  }

  return {
    dialogVisible,
    dialogMode,
    formData,
    openCreateDialog,
    openEditDialog,
    closeDialog
  }
}
