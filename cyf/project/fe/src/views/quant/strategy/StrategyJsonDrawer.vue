<template>
  <el-drawer
    v-model="open"
    title="rule_config JSON 抽屉"
    direction="rtl"
    size="560px"
    :destroy-on-close="false"
  >
    <template #header>
      <div class="json-drawer__header">
        <span>规则 JSON（逃生舱）</span>
        <el-button size="small" plain @click="formatNow">格式化</el-button>
      </div>
    </template>

    <div class="json-drawer__body">
      <el-alert
        v-if="parseError"
        :title="parseError"
        type="error"
        show-icon
        :closable="false"
        class="json-drawer__alert"
      />
      <el-alert
        v-else
        title="JSON 是唯一 source of truth，编辑会自动应用到面板。"
        type="info"
        show-icon
        :closable="false"
        class="json-drawer__alert"
      />
      <el-input
        v-model="text"
        type="textarea"
        :rows="22"
        spellcheck="false"
        class="json-drawer__textarea quant-code-input"
        @input="onInput"
      />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { RuleConfigV2 } from '@/composables/quant/strategyIdeTypes'

const props = defineProps<{ modelValue: RuleConfigV2 }>()
const emit = defineEmits<{ 'update:modelValue': [v: RuleConfigV2] }>()

const open = ref(false)
const text = ref(JSON.stringify(props.modelValue, null, 2))
const parseError = ref('')

watch(
  () => props.modelValue,
  (v) => {
    const next = JSON.stringify(v, null, 2)
    if (next !== text.value) text.value = next
  }
)

function onInput(v: string) {
  try {
    const parsed = JSON.parse(v)
    parseError.value = ''
    emit('update:modelValue', parsed)
  } catch (e: any) {
    parseError.value = `JSON 解析失败：${e?.message || String(e)}（当前内容已暂存，不会覆盖表单；修改后会重试）`
  }
}

function formatNow() {
  try {
    const parsed = JSON.parse(text.value)
    text.value = JSON.stringify(parsed, null, 2)
    parseError.value = ''
  } catch (e: any) {
    parseError.value = `JSON 解析失败：${e?.message || String(e)}`
  }
}

function show() {
  open.value = true
  text.value = JSON.stringify(props.modelValue, null, 2)
  parseError.value = ''
}

defineExpose({ show })
</script>

<style scoped>
.json-drawer__header {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 600;
}
.json-drawer__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}
.json-drawer__alert {
  flex-shrink: 0;
}
.json-drawer__textarea :deep(.el-textarea__inner) {
  font-family: var(--q-mono);
  font-size: 12px;
  line-height: 1.5;
  min-height: 60vh;
}
</style>