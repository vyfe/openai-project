<script setup lang="ts">
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'
const workbench = useQuantWorkbench()
</script>

<template>
  <section class="quant-panel">
    <div class="quant-panel__header"><h2>持仓流水</h2><el-button @click="workbench.resetPositionForm">新建流水</el-button></div>
    <el-form label-position="top" @submit.prevent="workbench.savePositionEntry">
      <div class="quant-form-grid quant-form-grid--three">
        <el-form-item label="标的"><el-select v-model="workbench.positionForm.symbol" filterable allow-create default-first-option><el-option v-for="item in workbench.symbolOptions" :key="item.symbol" :label="workbench.displaySymbol(item.symbol)" :value="item.symbol" /></el-select></el-form-item>
        <el-form-item label="方向"><el-select v-model="workbench.positionForm.side"><el-option label="买入" value="buy" /><el-option label="卖出" value="sell" /></el-select></el-form-item>
        <el-form-item label="数量"><el-input-number v-model="workbench.positionForm.quantity" :min="1" /></el-form-item>
        <el-form-item label="价格"><el-input-number v-model="workbench.positionForm.price" :min="0" :precision="4" /></el-form-item>
        <el-form-item label="发生时间"><el-date-picker v-model="workbench.positionForm.occurredAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="workbench.positionForm.remark" /></el-form-item>
      </div>
      <el-button native-type="submit" type="primary" :loading="workbench.loading.savingPosition">保存流水</el-button>
      <el-button v-if="workbench.positionForm.id" type="danger" @click="workbench.deleteSelectedPositionEntry">删除流水</el-button>
    </el-form>
    <el-table :data="workbench.positionJournal" stripe @row-click="workbench.hydratePositionForm">
      <el-table-column prop="occurred_at" label="时间" min-width="170" />
      <el-table-column prop="symbol" label="标的" /><el-table-column prop="side" label="方向" />
      <el-table-column prop="quantity" label="数量" /><el-table-column prop="price" label="价格" />
      <el-table-column prop="remark" label="备注" />
    </el-table>
  </section>
</template>
