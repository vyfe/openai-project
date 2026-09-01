<template>
  <div class="indicator-palette">
    <div class="indicator-palette__header">
      <div class="indicator-palette__header-row">
        <h4>指标</h4>
        <span class="indicator-palette__count">{{ ide.indicators.value.length }} 项</span>
      </div>
      <p class="indicator-palette__hint">
        点击输出名插入表达式；只有动态输出指标显示可编辑参数，固定算法指标使用系统内置参数。
      </p>
    </div>

    <div v-if="!ide.indicators.value.length && !ide.loading.meta" class="indicator-palette__empty">
      暂无指标 catalog，请确认后服务正常后刷新页面。
    </div>

    <div
      v-for="group in groupedIndicators"
      :key="group.category"
      class="indicator-palette__group"
    >
      <div class="indicator-palette__group-title">{{ categoryLabel(group.category) }}</div>

      <el-collapse v-model="openGroups" class="indicator-palette__collapse">
        <el-collapse-item
          v-for="spec in group.items"
          :key="spec.key"
          :name="spec.key"
        >
          <template #title>
            <span class="indicator-palette__item-title">
              <span class="indicator-palette__item-label">{{ spec.label }}</span>
              <code class="indicator-palette__item-key">{{ spec.key }}</code>
            </span>
          </template>
          <div v-if="!spec.params.length" class="indicator-palette__no-params">无参数</div>
          <div v-else-if="hasDynamicOutputs(spec)" class="indicator-palette__params">
            <div v-for="p in spec.params" :key="p.name" class="indicator-palette__param-row">
              <div class="indicator-palette__param-label">
                <span>{{ p.label }}</span>
                <el-tooltip
                  v-if="p.help"
                  :content="`${p.label}（${typeTypeName(p.type)}）\n${p.help}`"
                  placement="top"
                  :show-after="200"
                >
                  <el-icon class="indicator-palette__param-help"><QuestionFilled /></el-icon>
                </el-tooltip>
                <span class="indicator-palette__param-meta">
                  <el-tag size="small" type="info" effect="plain">{{ typeTypeName(p.type) }}</el-tag>
                  <span v-if="p.min != null || p.max != null" class="indicator-palette__param-range">
                    {{ formatRange(p.min, p.max) }}
                  </span>
                </span>
              </div>
              <div class="indicator-palette__param-input">
                <el-input-number
                  v-if="p.type === 'int'"
                  :model-value="Number(getParam(spec.key, p.name))"
                  :min="p.min ?? undefined"
                  :max="p.max ?? undefined"
                  size="small"
                  @update:model-value="(v: number | undefined) => ide.setIndicatorParam(spec.key, p.name, v)"
                />
                <el-input-number
                  v-else-if="p.type === 'float'"
                  :model-value="Number(getParam(spec.key, p.name))"
                  :min="p.min ?? undefined"
                  :max="p.max ?? undefined"
                  :step="0.1"
                  size="small"
                  @update:model-value="(v: number | undefined) => ide.setIndicatorParam(spec.key, p.name, v)"
                />
                <template v-else-if="p.type === 'int_list'">
                  <el-input
                    :model-value="formatIntList(getParam(spec.key, p.name))"
                    placeholder="5, 10, 20, 60"
                    size="small"
                    @update:model-value="(v: string) => ide.setIndicatorParam(spec.key, p.name, parseIntList(v))"
                  />
                </template>
                <span v-else class="indicator-palette__param-default">{{ formatValue(p.default) }}</span>
              </div>
            </div>
          </div>
          <div v-else class="indicator-palette__fixed-note">
            <span class="indicator-palette__fixed-badge">固定算法</span>
            <span>参数由系统内置，策略表达式直接使用下方固定输出。</span>
          </div>

          <div class="indicator-palette__outputs">
            <div class="indicator-palette__outputs-title">输出（点击插入）</div>
            <div class="indicator-palette__outputs-grid">
              <button
                v-for="out in spec.outputs"
                :key="out.name"
                type="button"
                class="indicator-palette__chip"
                @click="emit('insert', expandOutputName(spec.key, out.name))"
              >
                <code>{{ expandOutputName(spec.key, out.name) }}</code>
                <span class="indicator-palette__chip-label">{{ out.label }}</span>
              </button>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import type { useStrategyIde } from '@/composables/useStrategyIde'
import type { IndicatorSpec } from '@/composables/quant/strategyIdeTypes'

type Ide = ReturnType<typeof useStrategyIde>

const props = defineProps<{ ide: Ide }>()
const emit = defineEmits<{ insert: [text: string] }>()

const openGroups = ref<string[]>([])

watch(
  () => props.ide.indicators.value.map(i => i.key),
  (keys) => {
    // 元数据刷新后只保留仍然存在的展开项，避免窄栏默认铺开全部指标。
    openGroups.value = openGroups.value.filter(key => keys.includes(key))
  },
  { immediate: true }
)

const groupedIndicators = computed(() => {
  const map = new Map<string, { category: string; items: IndicatorSpec[] }>()
  for (const spec of props.ide.indicators.value) {
    const bucket = map.get(spec.category) || { category: spec.category, items: [] }
    bucket.items.push(spec)
    map.set(spec.category, bucket)
  }
  return Array.from(map.values())
})

function categoryLabel(cat: string) {
  const map: Record<string, string> = {
    trend: '趋势',
    momentum: '动量',
    volume: '成交量',
    structure: '结构',
    volatility: '波动'
  }
  return map[cat] || cat
}

function typeTypeName(t: string): string {
  const map: Record<string, string> = {
    int: '整数',
    float: '小数',
    int_list: '整数列表',
    bool: '布尔',
    enum: '枚举'
  }
  return map[t] || t
}

function formatRange(min: number | null | undefined, max: number | null | undefined): string {
  if (min != null && max != null) return `范围 ${min} ~ ${max}`
  if (min != null) return `≥ ${min}`
  if (max != null) return `≤ ${max}`
  return ''
}

function hasDynamicOutputs(spec: IndicatorSpec): boolean {
  return spec.outputs.some(output => output.name.includes('{'))
}

function getParam(key: string, paramName: string) {
  const spec = props.ide.indicators.value.find(i => i.key === key)
  if (!spec) return null
  const p = spec.params.find(p => p.name === paramName)
  if (!p) return null
  const ind = props.ide.form.rule_config.indicators.find(i => i.key === key)
  return ind?.params?.[paramName] ?? p.default
}

function expandOutputName(key: string, name: string): string {
  if (!name.includes('{')) return name
  // 把模板名里的占位符替换成当前已配置的 param（取第一项）
  const spec = props.ide.indicators.value.find(i => i.key === key)
  if (!spec) return name
  const ind = props.ide.form.rule_config.indicators.find(i => i.key === key)
  let out = name
  for (const p of spec.params) {
    const v = ind?.params?.[p.name] ?? p.default
    const first = Array.isArray(v) ? v[0] : v
    out = out.replace(p.name === 'windows' ? '{window}' : `{${p.name}}`, String(first))
  }
  return out
}

function formatValue(v: any): string {
  if (Array.isArray(v)) return v.join(', ')
  if (v === null || v === undefined) return '—'
  return String(v)
}

function formatIntList(v: any): string {
  if (Array.isArray(v)) return v.join(', ')
  return String(v ?? '')
}

function parseIntList(text: string): number[] {
  if (!text) return []
  return text
    .split(/[,，\s]+/)
    .map(s => Number(s))
    .filter(n => Number.isFinite(n))
}

</script>

<style scoped>
.indicator-palette {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.indicator-palette__header {
  padding-bottom: 10px;
  border-bottom: 1px solid color-mix(in srgb, var(--q-line) 76%, transparent);
}
.indicator-palette__header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.indicator-palette__header h4 {
  margin: 0;
  color: var(--q-ink);
  font-size: 14px;
  font-weight: 760;
  letter-spacing: 0.02em;
}
.indicator-palette__count {
  padding: 2px 7px;
  border: 1px solid color-mix(in srgb, var(--q-cyan) 32%, var(--q-line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--q-cyan) 8%, var(--q-surface));
  color: var(--q-cyan);
  font-family: var(--q-mono);
  font-size: 10px;
  line-height: 1.3;
}
.indicator-palette__hint {
  margin: 6px 0 0;
  color: var(--q-muted);
  font-size: 12px;
  line-height: 1.5;
}
.indicator-palette__empty {
  padding: 12px;
  color: var(--q-muted);
  font-size: 12px;
  border: 1px dashed var(--q-line);
  border-radius: 6px;
  text-align: center;
}
.indicator-palette__group {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.indicator-palette__group-title {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 0 1px;
  color: var(--q-ink);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
}
.indicator-palette__group-title::before {
  width: 3px;
  height: 14px;
  border-radius: 999px;
  background: var(--q-copper);
  content: '';
}
.indicator-palette__collapse {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border: 0;
  background: transparent;
}
.indicator-palette__collapse :deep(.el-collapse-item) {
  overflow: hidden;
  border: 1px solid var(--q-line);
  border-radius: 8px;
  background: color-mix(in srgb, var(--q-surface) 94%, var(--q-bg));
  transition: border-color 160ms ease, background 160ms ease, box-shadow 160ms ease;
}
.indicator-palette__collapse :deep(.el-collapse-item:hover) {
  border-color: var(--q-line-strong);
}
.indicator-palette__collapse :deep(.el-collapse-item.is-active) {
  border-color: color-mix(in srgb, var(--q-cyan) 54%, var(--q-line));
  background: color-mix(in srgb, var(--q-cyan) 5%, var(--q-surface));
  box-shadow: 0 6px 18px color-mix(in srgb, var(--q-cyan) 8%, transparent);
}
.indicator-palette__collapse :deep(.el-collapse-item__header) {
  height: 42px;
  padding: 0 10px;
  border: 0;
  background: transparent;
  color: var(--q-ink);
  font-size: 12px;
  font-weight: 650;
  line-height: 1;
}
.indicator-palette__collapse :deep(.el-collapse-item__header:hover) {
  background: color-mix(in srgb, var(--q-surface-2) 72%, transparent);
}
.indicator-palette__collapse :deep(.el-collapse-item__header:focus-visible) {
  outline: 2px solid color-mix(in srgb, var(--q-cyan) 72%, white);
  outline-offset: -2px;
}
.indicator-palette__collapse :deep(.el-collapse-item__arrow) {
  margin-left: 8px;
  color: var(--q-muted);
  font-size: 12px;
}
.indicator-palette__collapse :deep(.el-collapse-item__wrap) {
  border: 0;
  background: transparent;
}
.indicator-palette__collapse :deep(.el-collapse-item__content) {
  padding: 0 10px 12px;
  color: var(--q-ink);
}
.indicator-palette__item-title {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 7px;
}
.indicator-palette__item-label {
  overflow: hidden;
  color: var(--q-ink);
  font-size: 12px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.indicator-palette__item-key {
  flex: 0 0 auto;
  padding: 2px 5px;
  border: 1px solid var(--q-line);
  border-radius: 4px;
  background: var(--q-surface-2);
  color: var(--q-cyan);
  font-family: var(--q-mono);
  font-size: 10px;
  font-weight: 500;
}
.indicator-palette__params,
.indicator-palette__outputs {
  padding: 0;
}
.indicator-palette__param-row {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
  gap: 10px;
  align-items: end;
  padding: 8px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--q-line) 62%, transparent);
}
.indicator-palette__param-row:last-child {
  border-bottom: 0;
}
.indicator-palette__param-label {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
  color: var(--q-ink);
  font-size: 12px;
  line-height: 1.3;
}
.indicator-palette__param-help {
  margin-left: 2px;
  color: var(--q-muted);
  cursor: help;
  font-size: 11px;
}
.indicator-palette__param-help:hover {
  color: var(--q-copper);
}
.indicator-palette__param-meta {
  display: flex;
  min-width: 0;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  color: var(--q-muted);
  font-size: 11px;
}
.indicator-palette__param-range {
  font-family: var(--q-mono);
}
.indicator-palette__no-params {
  color: var(--q-muted);
  font-size: 12px;
}
.indicator-palette__fixed-note {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0 2px;
  color: var(--q-muted);
  font-size: 11px;
  line-height: 1.45;
}
.indicator-palette__fixed-badge {
  flex: 0 0 auto;
  padding: 2px 6px;
  border: 1px solid color-mix(in srgb, var(--q-copper) 40%, var(--q-line));
  border-radius: 4px;
  background: color-mix(in srgb, var(--q-copper) 8%, var(--q-surface-2));
  color: var(--q-copper);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.03em;
}
.indicator-palette__param-default {
  display: block;
  overflow: hidden;
  color: var(--q-muted);
  font-size: 12px;
  font-family: var(--q-mono);
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.indicator-palette__param-input {
  min-width: 0;
}
.indicator-palette__param-input :deep(.el-input),
.indicator-palette__param-input :deep(.el-input-number) {
  width: 100%;
}
.indicator-palette__param-input :deep(.el-input__wrapper) {
  background: var(--q-surface-2);
  box-shadow: 0 0 0 1px var(--q-line) inset;
}
.indicator-palette__param-input :deep(.el-input__wrapper:hover),
.indicator-palette__param-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--q-cyan) inset;
}
.indicator-palette__outputs-title {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-top: 10px;
  border-top: 1px solid color-mix(in srgb, var(--q-line) 62%, transparent);
  color: var(--q-muted);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  margin-bottom: 8px;
}
.indicator-palette__outputs-title::before {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--q-copper);
  content: '';
}
.indicator-palette__outputs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 6px;
}
.indicator-palette__chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  min-height: 48px;
  padding: 8px;
  border: 1px solid var(--q-line);
  border-radius: 6px;
  background: var(--q-surface-2);
  color: var(--q-ink);
  font-family: var(--q-mono);
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  transition: border-color 140ms ease, background 140ms ease, transform 140ms ease;
}
.indicator-palette__chip:hover {
  border-color: var(--q-cyan);
  background: color-mix(in srgb, var(--q-cyan) 8%, var(--q-surface-2));
  transform: translateY(-1px);
}
.indicator-palette__chip code {
  overflow-wrap: anywhere;
  color: var(--q-copper);
  font-size: 12px;
  line-height: 1.25;
}
.indicator-palette__chip-label {
  color: var(--q-muted);
  font-size: 10px;
  font-family: var(--q-body);
}

@media (max-width: 420px) {
  .indicator-palette__param-row {
    grid-template-columns: 1fr;
    gap: 6px;
  }
  .indicator-palette__param-default {
    text-align: left;
  }
}
</style>
