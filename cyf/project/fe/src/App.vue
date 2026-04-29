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
#app {
  font-family: "Noto Sans SC", 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  margin: 0;
  padding: 0;
  min-height: 100vh;
  background: transparent;
  position: relative;
  z-index: 1;
}

body {
  position: relative;
  min-height: 100vh;
  background: linear-gradient(135deg, #f0f7f9 0%, #e8f2f5 100%);
  overflow-x: hidden;
}

/* 日夜主题动态背景层 */
body::before,
body::after {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  transition: opacity 0.6s ease;
}

/* 日间模式：阳光半透明流动光晕 */
body::before {
  opacity: 1;
  background:
    radial-gradient(circle at 85% 12%, rgba(255, 223, 128, 0.36) 0%, rgba(255, 223, 128, 0.16) 26%, rgba(255, 223, 128, 0) 55%),
    radial-gradient(circle at 76% 18%, rgba(255, 240, 193, 0.22) 0%, rgba(255, 240, 193, 0) 44%),
    radial-gradient(circle at 12% 78%, rgba(255, 255, 255, 0.22) 0%, rgba(255, 255, 255, 0) 42%);
  animation: sunlight-drift 20s ease-in-out infinite alternate;
}

/* 夜间模式：星空半透明闪烁层 */
body::after {
  opacity: 0;
  background:
    radial-gradient(circle at 8% 16%, rgba(255, 255, 255, 0.72) 0 1px, transparent 1.5px),
    radial-gradient(circle at 22% 36%, rgba(222, 235, 255, 0.58) 0 1.2px, transparent 1.8px),
    radial-gradient(circle at 37% 12%, rgba(255, 255, 255, 0.66) 0 1px, transparent 1.6px),
    radial-gradient(circle at 54% 28%, rgba(209, 226, 255, 0.62) 0 1.1px, transparent 1.7px),
    radial-gradient(circle at 68% 16%, rgba(255, 255, 255, 0.72) 0 1px, transparent 1.5px),
    radial-gradient(circle at 82% 33%, rgba(221, 235, 255, 0.62) 0 1.2px, transparent 1.8px),
    radial-gradient(circle at 16% 66%, rgba(255, 255, 255, 0.66) 0 1px, transparent 1.6px),
    radial-gradient(circle at 32% 82%, rgba(211, 229, 255, 0.58) 0 1.1px, transparent 1.8px),
    radial-gradient(circle at 51% 74%, rgba(255, 255, 255, 0.72) 0 1px, transparent 1.5px),
    radial-gradient(circle at 70% 86%, rgba(224, 238, 255, 0.58) 0 1.2px, transparent 1.8px),
    radial-gradient(circle at 88% 72%, rgba(255, 255, 255, 0.64) 0 1px, transparent 1.6px),
    radial-gradient(ellipse at 80% -20%, rgba(122, 156, 204, 0.34) 0%, rgba(122, 156, 204, 0) 58%);
  animation: starlight-twinkle 4.6s ease-in-out infinite alternate, starlight-drift 65s linear infinite;
}

/* 基础字体大小变量和Element Plus支持 */
:root {
  --message-font-size-small: 13px;
  --message-font-size-medium: 16px;
  --message-font-size-large: 20px;

  /* 为Element Plus组件添加字体大小支持 */
  --el-font-size-base: var(--message-font-size-medium);
  --el-font-size-extra-small: calc(var(--message-font-size-medium) * 0.75);
  --el-font-size-small: calc(var(--message-font-size-medium) * 0.875);
  --el-font-size-medium: var(--message-font-size-medium);
  --el-font-size-large: calc(var(--message-font-size-medium) * 1.25);
  --el-font-size-extra-large: calc(var(--message-font-size-medium) * 1.5);
}

/* 全局深色主题样式 */
body.dark-theme {
  background-color: #1a1a1a;
  color: #e0e0e0;
}

body.dark-theme::before {
  opacity: 0;
}

body.dark-theme::after {
  opacity: 0.78;
}

/* Element Plus 禁用状态 CSS 变量 - 夜间模式 */
body.dark-theme {
  --el-disabled-bg-color: #2a2a2a;
  --el-disabled-border-color: #555555;
  --el-disabled-text-color: #9a9a9a;
}

body.dark-theme .el-input.is-disabled .el-input__inner {
  color: #9a9a9a !important;
  -webkit-text-fill-color: #9a9a9a !important;
}

/* Element Plus 组件深色主题覆盖 */
body.dark-theme .el-button {
  background-color: #333333;
  border-color: #555555;
  color: #e0e0e0;
}

body.dark-theme .el-button--primary {
  background: linear-gradient(135deg, #5a7bc1 0%, #7a9ccc 100%);
  border-color: #5a7bc1;
  color: white;
}

body.dark-theme .el-button--primary:hover {
  background: linear-gradient(135deg, #6a8bc1 0%, #8aaecc 100%);
  border-color: #6a8bc1;
}

body.dark-theme .el-button--danger {
  background-color: #5a3232;
  border-color: #7a4242;
  color: white;
}

/* Element Plus 2.x 新版 el-select 收起状态样式 */
body.dark-theme .el-select__wrapper {
  background-color: #333333;
  box-shadow: 0 0 0 1px #555555 inset;
}

body.dark-theme .el-select__wrapper:hover {
  box-shadow: 0 0 0 1px #7a9ccc inset;
}

body.dark-theme .el-select__selection,
body.dark-theme .el-select__selected-item {
  color: #e0e0e0;
}

body.dark-theme .el-select__placeholder {
  color: #9a9a9a;
}

body.dark-theme .el-select__caret {
  color: #9a9a9a;
}

body.dark-theme .el-select__input {
  color: #e0e0e0;
  background-color: transparent;
}

body.dark-theme .el-select-dropdown {
  background-color: #222222;
  border: 1px solid #555555;
  color: #e0e0e0;
}

body.dark-theme .el-select-dropdown__item {
  color: #e0e0e0;
  background-color: #222222;
}

body.dark-theme .el-select-dropdown__item.hover,
body.dark-theme .el-select-dropdown__item:hover {
  background-color: #333333;
}

body.dark-theme .el-slider__runway {
  background-color: #555555;
}

body.dark-theme .el-slider__bar {
  background-color: #7a9ccc;
}

body.dark-theme .el-slider__button {
  background-color: #7a9ccc;
  border: 2px solid #90d8ff;
}

body.dark-theme .el-tag {
  background-color: #333333;
  border-color: #555555;
  color: #e0e0e0;
}

body.dark-theme .el-popover,
body.dark-theme .el-popconfirm {
  background-color: #222222;
  border: 1px solid #555555;
  color: #e0e0e0;
}

/* Teleport 到 body 的各类浮层统一暗色样式（tooltip/popconfirm/popover/select/dropdown） */
body.dark-theme .el-popper,
body.dark-theme .el-tooltip__popper,
body.dark-theme .el-popover.el-popper,
body.dark-theme .el-popconfirm.el-popper,
body.dark-theme .el-select__popper,
body.dark-theme .el-dropdown__popper {
  background-color: #222222 !important;
  border: 1px solid #555555 !important;
  color: #e0e0e0 !important;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.35) !important;
}

body.dark-theme .el-popper * {
  color: inherit;
}

body.dark-theme .el-popper__arrow::before {
  background-color: #222222 !important;
  border-color: #555555 !important;
}

body.dark-theme .el-popconfirm__main {
  color: #e0e0e0 !important;
}

body.dark-theme .el-popconfirm__icon {
  color: #f59e0b !important;
}

body.dark-theme .el-popconfirm__action .el-button--default {
  background-color: #333333 !important;
  border-color: #555555 !important;
  color: #e0e0e0 !important;
}

body.dark-theme .el-dialog {
  background-color: #222222;
  border: 1px solid #555555;
  color: #e0e0e0;
}

body.dark-theme .el-dialog__header,
body.dark-theme .el-dialog__body,
body.dark-theme .el-dialog__footer {
  color: #e0e0e0;
  border-color: #555555 !important;
}

body.dark-theme .el-overlay-dialog {
  background: rgba(0, 0, 0, 0.55);
}

body.dark-theme .el-switch__core {
  background-color: #555555;
  border-color: #555555;
}

body.dark-theme .el-switch.is-checked .el-switch__core {
  background-color: #7a9ccc;
  border-color: #7a9ccc;
}

body.dark-theme .el-radio-button__inner {
  background-color: #333333;
  border-color: #555555;
  color: #e0e0e0;
}

body.dark-theme .el-radio-button__inner:hover {
  background-color: #444444;
  color: #e0e0e0;
}

body.dark-theme .el-radio-button.is-active .el-radio-button__inner {
  background-color: #5a7bc1;
  border-color: #7a9ccc;
  color: white;
}

body.dark-theme .el-checkbox__input .el-checkbox__inner {
  background-color: #333333;
  border: 1px solid #555555;
}

body.dark-theme .el-checkbox__input.is-checked .el-checkbox__inner {
  background-color: #7a9ccc;
  border-color: #7a9ccc;
}

body.dark-theme .el-upload-dragger {
  background-color: #333333;
  border: 1px dashed #555555;
  color: #e0e0e0;
}

body.dark-theme .el-upload-dragger:hover {
  border-color: #7a9ccc;
}

body.dark-theme .el-dropdown-menu {
  background-color: #222222;
  border: 1px solid #555555;
  color: #e0e0e0;
}

body.dark-theme .el-dropdown-menu__item {
  color: #e0e0e0;
}

body.dark-theme .el-dropdown-menu__item:hover {
  background-color: #333333;
}

body.dark-theme .el-message-box {
  background-color: #222222;
  border: 1px solid #555555;
  color: #e0e0e0;
}

body.dark-theme .custom-dark-tooltip .el-tooltip__popper .popper__arrow {
  background-color: #333 !important; /* 修改菱形颜色 */
}

/* 管理后台暗色兜底：避免部分 Element Plus 组件维持浅色底 */
body.dark-theme .admin-page .el-table,
body.dark-theme .admin-page .el-table__inner-wrapper,
body.dark-theme .admin-page .el-table__header-wrapper,
body.dark-theme .admin-page .el-table__body-wrapper,
body.dark-theme .admin-page .el-table tr,
body.dark-theme .admin-page .el-table th.el-table__cell,
body.dark-theme .admin-page .el-table td.el-table__cell {
  background-color: #222222 !important;
  color: #e0e0e0 !important;
  border-color: #555555 !important;
}

body.dark-theme .admin-page .el-table th.el-table__cell {
  background-color: #2a2a2a !important;
  color: #aaaaaa !important;
}

body.dark-theme .admin-page .el-table__empty-block,
body.dark-theme .admin-page .el-empty__description {
  background-color: #222222 !important;
  color: #9a9a9a !important;
}

@keyframes sunlight-drift {
  0% {
    transform: translate3d(-1.2%, 0, 0) scale(1);
    filter: saturate(100%);
  }
  50% {
    transform: translate3d(0.8%, -1%, 0) scale(1.03);
    filter: saturate(108%);
  }
  100% {
    transform: translate3d(1.5%, 1.2%, 0) scale(1.05);
    filter: saturate(102%);
  }
}

@keyframes starlight-twinkle {
  0% {
    opacity: 0.5;
  }
  100% {
    opacity: 0.9;
  }
}

@keyframes starlight-drift {
  0% {
    transform: translateY(0);
  }
  100% {
    transform: translateY(8px);
  }
}

@media (prefers-reduced-motion: reduce) {
  body::before,
  body::after {
    animation: none !important;
  }
}
</style>
