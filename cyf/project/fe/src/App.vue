<template>
  <div id="app">
    <router-view></router-view>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import VersionService from './services/version';
import { useThemeManager } from '@/composables/useThemeManager';

const { initThemeManager } = useThemeManager();

onMounted(() => {
  // 检查版本更新并处理缓存
  VersionService.checkAndHandleVersionChange();
  // 初始化全局主题管理，统一日夜模式状态和DOM类
  initThemeManager();
});
</script>

<style>
@import "tailwindcss";
@tailwind base;
@tailwind components;
@tailwind utilities;
@import "@/styles/tokens.css";
@import "@/styles/theme-light.css";
@import "@/styles/theme-dark.css";
#app {
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  margin: 0;
  padding: 0;
  height: 100vh;
  background: var(--bg-app-gradient);
}

body.dark-theme .el-input.is-disabled .el-input__inner {
  color: var(--el-disabled-text-color) !important;
  -webkit-text-fill-color: var(--el-disabled-text-color) !important;
}

/* Element Plus dark theme unified by tokens */
body.dark-theme .el-button,
body.dark-theme .el-select__wrapper,
body.dark-theme .el-tag,
body.dark-theme .el-dialog,
body.dark-theme .el-dropdown-menu,
body.dark-theme .el-message-box,
body.dark-theme .el-upload-dragger,
body.dark-theme .el-popover,
body.dark-theme .el-popconfirm,
body.dark-theme .el-select-dropdown {
  background-color: var(--bg-1);
  border-color: var(--line-1);
  color: var(--text-1);
}

body.dark-theme .el-select__wrapper:hover,
body.dark-theme .el-upload-dragger:hover {
  border-color: var(--accent-1);
  box-shadow: 0 0 0 1px var(--accent-1) inset;
}

body.dark-theme .el-button--primary {
  background: linear-gradient(135deg, var(--accent-1) 0%, var(--el-color-primary-light-3) 100%);
  border-color: var(--accent-1);
  color: #fff;
}

body.dark-theme .el-button--primary:hover {
  background: linear-gradient(135deg, var(--el-color-primary-light-3) 0%, var(--el-color-primary-light-5) 100%);
  border-color: var(--el-color-primary-light-3);
}

body.dark-theme .el-slider__runway,
body.dark-theme .el-switch__core,
body.dark-theme .el-checkbox__input .el-checkbox__inner,
body.dark-theme .el-radio-button__inner {
  background-color: var(--bg-2);
  border-color: var(--line-1);
  color: var(--text-1);
}

body.dark-theme .el-slider__bar,
body.dark-theme .el-slider__button,
body.dark-theme .el-switch.is-checked .el-switch__core,
body.dark-theme .el-checkbox__input.is-checked .el-checkbox__inner,
body.dark-theme .el-radio-button.is-active .el-radio-button__inner {
  background-color: var(--accent-1);
  border-color: var(--accent-1);
}

body.dark-theme .el-slider__button {
  border-width: 2px;
  border-style: solid;
  border-color: var(--accent-2);
}

body.dark-theme .el-select__selection,
body.dark-theme .el-select__selected-item,
body.dark-theme .el-select__input,
body.dark-theme .el-dialog__header,
body.dark-theme .el-dialog__body,
body.dark-theme .el-dialog__footer,
body.dark-theme .el-dropdown-menu__item,
body.dark-theme .el-popconfirm__main {
  color: var(--text-1);
}

body.dark-theme .el-select__placeholder,
body.dark-theme .el-select__caret {
  color: var(--text-2);
}

body.dark-theme .el-popper,
body.dark-theme .el-tooltip__popper,
body.dark-theme .el-popover.el-popper,
body.dark-theme .el-popconfirm.el-popper,
body.dark-theme .el-select__popper,
body.dark-theme .el-dropdown__popper {
  background-color: var(--bg-1) !important;
  border: 1px solid var(--line-1) !important;
  color: var(--text-1) !important;
}

body.dark-theme .el-popper__arrow::before {
  background-color: var(--bg-1) !important;
  border-color: var(--line-1) !important;
}

body.dark-theme .el-overlay-dialog {
  background: rgba(0, 0, 0, 0.45);
}

body.dark-theme .admin-page .el-table,
body.dark-theme .admin-page .el-table__inner-wrapper,
body.dark-theme .admin-page .el-table__header-wrapper,
body.dark-theme .admin-page .el-table__body-wrapper,
body.dark-theme .admin-page .el-table tr,
body.dark-theme .admin-page .el-table th.el-table__cell,
body.dark-theme .admin-page .el-table td.el-table__cell,
body.dark-theme .admin-page .el-table__empty-block,
body.dark-theme .admin-page .el-empty__description {
  background-color: var(--bg-1) !important;
  color: var(--text-1) !important;
  border-color: var(--line-1) !important;
}

body.dark-theme .admin-page .el-table th.el-table__cell {
  background-color: var(--bg-2) !important;
  color: var(--text-2) !important;
}

</style>
