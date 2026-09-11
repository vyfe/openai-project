<template>
  <div class="quant-pool-select">
    <el-select
      :model-value="modelValue"
      multiple
      filterable
      :remote="remote"
      :remote-method="remoteMethodProxy"
      :reserve-keyword="reserveKeyword"
      :allow-create="allowCreate"
      :default-first-option="allowCreate"
      collapse-tags
      collapse-tags-tooltip
      :placeholder="allActive ? placeholderAllActive : placeholder"
      :disabled="allActive"
      class="quant-pool-select__inner"
      v-bind="$attrs"
      @update:model-value="onChange"
    >
      <el-option
        v-for="item in options"
        :key="getKey(item)"
        :label="formatLabelFn(item)"
        :value="getValue(item)"
      />
    </el-select>
    <el-checkbox
      :model-value="allActive"
      class="quant-pool-select__all"
      :disabled="modelValue && modelValue.length > 0"
      @update:model-value="onAllActiveChange"
    >
      {{ allActiveText }}
    </el-checkbox>
  </div>
</template>

<script setup lang="ts">
/**
 * 量化标的池多选下拉 —— 统一"不选=全选"语义。
 *
 * 行为约定：
 * - 用户从下拉选了 N 个 → modelValue = [N 个]，allActive = false
 * - 用户勾"拉取全部" → modelValue = []，allActive = true（下拉禁用，徽标提示）
 * - 用户已选了 → "全部"复选框自动禁用（避免两个状态同时为真）
 * - 上层拿到 modelValue + allActive 即可：
 *     - allActive 为 true → 提交时 payload 走全表（无需 symbols）
 *     - modelValue 非空 → 走指定列表
 *     - 两者皆空 → 抛错（前端兜底校验）
 */
import { computed } from 'vue'

interface SelectOption {
  symbol?: string
  code?: string
  name?: string
  custom_name?: string
  display_name?: string
}

const props = withDefaults(defineProps<{
  /** 绑定的已选 symbol 数组 */
  modelValue: string[]
  /** 是否处于"全表拉取"模式 */
  allActive: boolean
  /** 可选项列表（含 display_name 用于渲染） */
  options: SelectOption[]
  /** "全部"复选框文案 */
  allActiveText?: string
  /** 正常 placeholder */
  placeholder?: string
  /** allActive 时的 placeholder */
  placeholderAllActive?: string
  /** 取值的 key（默认取 symbol 字段） */
  valueKey?: keyof SelectOption
  /** 渲染 label（默认 name/code 兼容，外部可覆盖） */
  formatLabel?: (item: SelectOption) => string
  /** 远程搜索模式：true 时调用方需通过 remoteMethod 提供回调 */
  remote?: boolean
  remoteMethod?: (keyword: string) => void
  reserveKeyword?: boolean
  allowCreate?: boolean
}>(), {
  allActiveText: '拉取全部 active 标的',
  placeholder: '选择标的（不选 = 拉取全部）',
  placeholderAllActive: '已选"全部"——忽略此栏',
  valueKey: 'symbol',
  formatLabel: undefined,
  remote: false,
  remoteMethod: undefined,
  reserveKeyword: false,
  allowCreate: false
})

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
  'update:allActive': [value: boolean]
}>()

function getKey(item: SelectOption): string {
  return String((item as any)[props.valueKey] ?? '')
}

function getValue(item: SelectOption): string {
  return String((item as any)[props.valueKey] ?? '')
}

const _defaultFormat = (item: SelectOption): string => {
  // 优先 display_name → name → code
  const display = item.display_name || item.name || ''
  const code = item.symbol || item.code || ''
  if (!display) return code
  if (display === code) return code
  if (display.includes(code)) return display
  return `${display}（${code}）`
}

const formatLabelFn = computed(() => props.formatLabel || _defaultFormat)

// el-select remote-method 在 multiple 模式下需要的入参是字符串 keyword；
// 直接透传避免触发额外的 props 重命名。
const remoteMethodProxy = (keyword: string) => {
  if (props.remoteMethod) props.remoteMethod(keyword)
}

function onChange(value: string[]) {
  // 用户在下拉里选了若干；勾掉所有 → allActive 仍为 false，由上层决定怎么兜底
  emit('update:modelValue', value || [])
  if (value && value.length > 0 && props.allActive) {
    // 不太可能：用户在禁用态还能 emit change；兜底把 allActive 关掉
    emit('update:allActive', false)
  }
}

function onAllActiveChange(value: boolean) {
  if (value) {
    // 切到全表：清空已选
    emit('update:modelValue', [])
  }
  emit('update:allActive', value)
}
</script>

<style scoped>
.quant-pool-select {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}
.quant-pool-select__inner {
  width: 100%;
}
.quant-pool-select__all {
  font-size: 12px;
  color: var(--q-muted);
}
</style>
