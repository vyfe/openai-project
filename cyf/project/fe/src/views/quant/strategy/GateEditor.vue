<template>
  <div class="gate-editor">
    <div class="gate-editor__title">组合门控</div>
    <el-radio-group :model-value="gate.mode" @update:model-value="onMode" class="gate-editor__modes">
      <el-radio-button label="all" value="all">全部通过</el-radio-button>
      <el-radio-button label="any" value="any">任一通过</el-radio-button>
      <el-radio-button label="expr" value="expr">自定义表达式</el-radio-button>
    </el-radio-group>
    <div v-if="gate.mode === 'expr'" class="gate-editor__expr">
      <el-input
        :model-value="gate.expr || ''"
        placeholder="例如：r1 and (r2 or r3)"
        size="small"
        @update:model-value="(v: string) => emit('update', { expr: v })"
      />
      <div class="gate-editor__hint">
        引用规则 id（如 r1、r2）；未列出的 id 视为 False。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { GateSpec, GateMode } from '@/composables/quant/strategyIdeTypes'

const props = defineProps<{ gate: GateSpec }>()
const emit = defineEmits<{ update: [patch: Partial<GateSpec>] }>()

function onMode(mode: GateMode | string | number | boolean | undefined) {
  emit('update', { mode: mode as GateMode, expr: mode === 'expr' ? (props.gate.expr || '') : null })
}
</script>

<style scoped>
.gate-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.gate-editor__title {
  color: var(--q-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.gate-editor__expr { display: flex; flex-direction: column; gap: 4px; }
.gate-editor__hint {
  color: var(--q-muted);
  font-size: 11px;
  line-height: 1.45;
}
</style>