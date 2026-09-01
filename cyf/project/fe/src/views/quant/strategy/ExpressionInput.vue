<template>
  <div class="expression-input" :class="{ 'is-error': !!errorText }">
    <el-input
      ref="inputRef"
      v-model="text"
      type="textarea"
      :rows="rows"
      :placeholder="placeholder"
      class="quant-code-input expression-input__textarea"
      @input="onInput"
    />
    <div v-if="errorText" class="expression-input__error">
      <el-icon><WarningFilled /></el-icon>
      <span>{{ errorText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { WarningFilled } from '@element-plus/icons-vue'
import type { ExpressionMeta } from '@/composables/quant/strategyIdeTypes'

const props = defineProps<{
  modelValue: string
  meta: ExpressionMeta
  error?: string
  rows?: number
  placeholder?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [v: string] }>()

const text = ref(props.modelValue || '')

watch(() => props.modelValue, (v) => {
  if (v !== text.value) text.value = v || ''
})

function onInput(v: string) {
  text.value = v
  emit('update:modelValue', v)
}

const errorText = computed(() => {
  if (props.error) return props.error
  const t = text.value.trim()
  if (!t) return ''
  let depth = 0
  for (const ch of t) {
    if (ch === '(') depth++
    else if (ch === ')') {
      depth--
      if (depth < 0) return '括号不匹配：多余的右括号'
    }
  }
  if (depth > 0) return '括号不匹配：缺少右括号'
  return ''
})
</script>

<style scoped>
.expression-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.expression-input.is-error :deep(.el-textarea__inner) {
  border-color: var(--q-red);
}
.expression-input__error {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--q-red);
  font-size: 12px;
}
.expression-input__textarea :deep(.el-textarea__inner) {
  font-family: var(--q-mono);
  font-size: 13px;
  line-height: 1.45;
}
</style>