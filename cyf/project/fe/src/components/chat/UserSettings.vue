<template>
  <el-dialog
    v-model="showDialog"
    :title="$t('chat.userSettings')"
    width="400px"
    :close-on-click-modal="false"
    :before-close="handleClose"
    class="user-settings-dialog"
  >
    <el-form
      :model="form"
      :rules="rules"
      ref="formRef"
      label-position="top"
      @submit.prevent="handleSubmit"
    >
      <el-form-item :label="$t('chat.currentPassword')" prop="currentPassword">
        <el-input
          v-model="form.currentPassword"
          type="password"
          show-password
          :placeholder="$t('chat.enterCurrentPassword')"
        />
      </el-form-item>

      <el-form-item :label="$t('chat.newPassword')" prop="newPassword">
        <el-input
          v-model="form.newPassword"
          type="password"
          show-password
          :placeholder="$t('chat.enterNewPassword')"
        />
      </el-form-item>

      <el-form-item :label="$t('chat.confirmNewPassword')" prop="confirmNewPassword">
        <el-input
          v-model="form.confirmNewPassword"
          type="password"
          show-password
          :placeholder="$t('chat.confirmNewPassword')"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">{{ $t('chat.cancel') }}</el-button>
        <el-button
          type="primary"
          @click="handleSubmit"
          :loading="loading"
        >
          {{ $t('chat.updatePassword') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, defineProps, defineEmits } from 'vue'
import { ElMessage, FormInstance, FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../../stores/auth'
import { chatAPI, authAPI } from '../../services/api'

const { t } = useI18n()
const authStore = useAuthStore()

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'passwordUpdated': []
}>()

const showDialog = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value)
})

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  currentPassword: '',
  newPassword: '',
  confirmNewPassword: ''
})

const validatePassword = (rule: any, value: string, callback: Function) => {
  if (value === '') {
    callback(new Error(t('chat.passwordRequired')))
  } else if (value.length < 6) {
    callback(new Error(t('chat.passwordTooShort')))
  } else {
    callback()
  }
}

const validateConfirmPassword = (rule: any, value: string, callback: Function) => {
  if (value === '') {
    callback(new Error(t('chat.confirmPasswordRequired')))
  } else if (value !== form.newPassword) {
    callback(new Error(t('chat.passwordsNotMatch')))
  } else {
    callback()
  }
}

const rules = reactive<FormRules>({
  currentPassword: [
    { required: true, validator: validatePassword, trigger: 'blur' }
  ],
  newPassword: [
    { required: true, validator: validatePassword, trigger: 'blur' }
  ],
  confirmNewPassword: [
    { required: true, validator: validateConfirmPassword, trigger: 'blur' }
  ]
})

const handleSubmit = async () => {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    // 先验证当前密码
    const loginResult = await authAPI.login(authStore.user, form.currentPassword)
    if (!loginResult.success) {
      ElMessage.error(loginResult.msg || t('chat.currentPasswordIncorrect'))
      return
    }

    // 重置密码
    const resetResult = await chatAPI.resetPassword(form.newPassword)
    if (resetResult.success) {
      ElMessage.success(resetResult.msg || t('chat.passwordUpdatedSuccessfully'))
      emit('passwordUpdated')
      showDialog.value = false
      // 清空表单
      form.currentPassword = ''
      form.newPassword = ''
      form.confirmNewPassword = ''
    } else {
      ElMessage.error(resetResult.msg || t('chat.updatePasswordFailed'))
    }
  } catch (error) {
    console.error('Update password error:', error)
    ElMessage.error(t('chat.updatePasswordFailed'))
  } finally {
    loading.value = false
  }
}

const handleClose = () => {
  showDialog.value = false
  // 清空表单但不触发表单验证
  Object.assign(form, {
    currentPassword: '',
    newPassword: '',
    confirmNewPassword: ''
  })
  if (formRef.value) {
    formRef.value.clearValidate()
  }
}
</script>

<style scoped>
@import '@/styles/user-settings.css';
</style>