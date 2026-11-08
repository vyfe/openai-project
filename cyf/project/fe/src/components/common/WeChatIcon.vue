<template>
  <svg
    class="wechat-icon"
    :class="`wechat-icon--${size}`"
    viewBox="0 0 32 32"
    role="img"
    :aria-label="label || undefined"
    :aria-hidden="label ? undefined : 'true'"
    focusable="false"
  >
    <!-- 后排大气泡：微信品牌绿 -->
    <path
      class="wechat-icon__bubble"
      fill="currentColor"
      d="M13.3 3.4c-5.9 0-10.7 3.9-10.7 8.8 0 2.8 1.5 5.2 3.8 6.8l-1 3.7 4.1-2.3c1.1.3 2.4.5 3.7.5h.4a6.7 6.7 0 0 1-.2-1.7c0-3.6 3.6-6.6 8.1-6.6h.4C20.4 7.2 17.1 3.4 13.3 3.4Z"
    />
    <circle class="wechat-icon__eye" cx="9.2" cy="10.2" r="1.35" />
    <circle class="wechat-icon__eye" cx="15.5" cy="10.2" r="1.35" />

    <!-- 前排小气泡：白底 + 同色描边 -->
    <path
      class="wechat-icon__bubble wechat-icon__bubble--front"
      fill="var(--wechat-cutout, #fff)"
      stroke="currentColor"
      stroke-width="1.9"
      stroke-linejoin="round"
      d="M22.6 12.1c-3.8 0-6.9 2.6-6.9 5.7s3.1 5.7 6.9 5.7c.9 0 1.8-.1 2.6-.4l3 1.6-.9-2.6c1.4-1.1 2.3-2.6 2.3-4.3 0-3.1-3.1-5.7-7-5.7Z"
    />
    <circle class="wechat-icon__eye wechat-icon__eye--front" cx="20" cy="16.5" r="1.15" />
    <circle class="wechat-icon__eye wechat-icon__eye--front" cx="25.2" cy="16.5" r="1.15" />
  </svg>
</template>

<script setup lang="ts">
/**
 * 微信图标：后排绿泡 + 前排白泡的通用标记。
 *
 * 用 currentColor 跟随所在文字颜色；前排气泡的填充用 `--wechat-cutout`
 * 变量兜底为白色，需要在深色底上显示时由使用方覆盖该变量。
 */
withDefaults(defineProps<{
  size?: 'sm' | 'md' | 'lg'
  label?: string
}>(), {
  size: 'md',
  label: ''
})
</script>

<style scoped>
.wechat-icon {
  display: inline-block;
  vertical-align: -0.14em;
  flex-shrink: 0;
  color: #07c160;
}

.wechat-icon--sm {
  width: 14px;
  height: 14px;
}

.wechat-icon--md {
  width: 17px;
  height: 17px;
}

.wechat-icon--lg {
  width: 22px;
  height: 22px;
}

.wechat-icon__eye {
  fill: var(--wechat-cutout, #fff);
}

.wechat-icon__eye--front {
  fill: currentColor;
}
</style>
