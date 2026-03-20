<template>
  <header
    class="relative z-10 border-b border-white/10 flex items-center justify-between px-6 shrink-0 bg-cover bg-left-top"
    :style="{ backgroundImage: `url(${bgMask})`, paddingTop: 'env(safe-area-inset-top)', height: 'calc(4rem + env(safe-area-inset-top))' }"
  >
    <!-- 左侧：返回箭头或占位 -->
    <div class="w-7 h-7 shrink-0">
      <button
        v-if="showBack"
        class="w-7 h-7 flex items-center justify-center hover:opacity-70 transition-opacity rounded-full"
        @click="goBack()"
        aria-label="返回"
      >
        <img :src="backArrow" alt="返回" class="w-[100%] h-[100%] object-contain" />
      </button>
    </div>

    <!-- 中间：标题 -->
    <div class="absolute left-1/2 -translate-x-1/2 select-none pointer-events-none">
      <h1
        class="text-xl font-bold whitespace-nowrap"
        style="background: linear-gradient(181deg, #ffffff 7%, #c7c8ff 98%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;"
      >{{ title }}</h1>
    </div>

    <!-- 右侧：自定义插槽 -->
    <div class="w-10 h-10 shrink-0 flex items-center justify-end">
      <slot name="right" />
    </div>
  </header>
</template>

<script setup>
import bgMask from '../assets/common/bg-mask.png'
import backArrow from '../assets/common/back-arrow.svg'
import { useRouter } from 'vue-router'

const router = useRouter()

defineProps({
  title: { type: String, required: true },
  showBack: { type: Boolean, default: false },
})

function goBack() {
  router.back()
}
</script>
