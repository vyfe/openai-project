<template>
  <div id="app">
    <router-view></router-view>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import VersionService from './services/version';

onMounted(() => {
  // 检查版本更新并处理缓存
  VersionService.checkAndHandleVersionChange();
});
</script>

<style>
@import "tailwindcss";
@tailwind base;
@tailwind components;
@tailwind utilities;
#app {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  margin: 0;
  padding: 0;
  height: 100vh;
  background: linear-gradient(135deg, #f0f7f9 0%, #e8f2f5 100%);
}

/* * {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  margin: 0;
  padding: 0;
  height: 100vh;
  overflow: hidden;
}

/* 全局深色主题样式 */
body.dark-theme {
  background-color: #1a1a1a;
  color: #000000;
}

/* Element Plus 禁用状态 CSS 变量 - 夜间模式 */
body.dark-theme {
  --el-disabled-bg-color: #2a2a2a;
  --el-disabled-border-color: #555555;
  --el-disabled-text-color: #9a9a9a;
}

/* Element Plus 禁用状态样式 - 夜间模式 */
body.dark-theme .el-textarea.is-disabled .el-textarea__inner {
  background-color: #2a2a2a !important;
  box-shadow: 0 0 0 1px #555555 inset !important;
  color: #9a9a9a !important;
  cursor: not-allowed !important;
}

/* Element Plus input 禁用状态 - 夜间模式 */
body.dark-theme .el-input.is-disabled .el-input__wrapper {
  background-color: #2a2a2a !important;
  box-shadow: 0 0 0 1px #555555 inset !important;
  cursor: not-allowed !important;
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

body.dark-theme .el-input__wrapper,
body.dark-theme .el-textarea__wrapper {
  background-color: #333333;
  border: 1px solid #555555;
  color: #e0e0e0;
  box-shadow: none;
}

body.dark-theme .el-input__wrapper:hover,
body.dark-theme .el-textarea__wrapper:hover {
  border-color: #7a9ccc;
}

body.dark-theme .el-input__inner,
body.dark-theme .el-textarea__inner {
  background-color: #333333;
  color: #e0e0e0;
}

body.dark-theme .el-select .el-input__wrapper {
  background-color: #333333;
  border: 1px solid #555555;
  color: #e0e0e0;
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

body.dark-theme .el-dialog {
  background-color: #222222;
  border: 1px solid #555555;
  color: #e0e0e0;
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
} */
</style>