// 版本管理服务
// 用于处理前端资源版本控制和缓存刷新
import { ref } from 'vue';

class VersionService {
  private static readonly VERSION_KEY = 'app_version';
  private static readonly BUILD_TIME_KEY = 'build_time';

  // 从构建时注入的版本信息
  static getCurrentVersion(): string {
    // 使用构建时的时间戳或hash
    // 如果没有构建版本，则使用时间戳
    return typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : Date.now().toString();
  }

  static getBuildTime(): string {
    return typeof __BUILD_TIME__ !== 'undefined' ? __BUILD_TIME__ : new Date().toISOString();
  }

  static checkAndHandleVersionChange(): void {
    const storedVersion = localStorage.getItem(this.VERSION_KEY);
    const buildTime = ref(localStorage.getItem(this.BUILD_TIME_KEY) || '');
    const currentVersion = this.getCurrentVersion();
    const currentBuildTime = this.getBuildTime();

    if (storedVersion && (storedVersion !== currentVersion || (currentVersion.endsWith('-SNAPSHOT') && buildTime.value !== currentBuildTime ))) {
      // 版本发生变化，清除相关缓存
      this.clearCache();
      // 存储新版本
      localStorage.setItem(this.VERSION_KEY, currentVersion);
      localStorage.setItem(this.BUILD_TIME_KEY, this.getBuildTime());
      console.log('应用已更新，已清除缓存');
    } else if (!storedVersion) {
      // 首次访问，存储版本信息
      localStorage.setItem(this.VERSION_KEY, currentVersion);
      localStorage.setItem(this.BUILD_TIME_KEY, this.getBuildTime());
    }
  }

  private static clearCache(): void {
    // 清除可能的缓存数据
    try {
      // 清除indexedDB、cache API等
      if ('caches' in window) {
        caches.keys().then(names => {
          names.forEach(name => {
            caches.delete(name);
          });
        });
      }
    } catch (e) {
      console.warn('清除缓存时出错:', e);
    }
  }

  // 生成带版本参数的URL
  static addVersionParam(url: string): string {
    const version = this.getCurrentVersion();
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}v=${version}`;
  }

  // 获取版本信息
  static getVersionInfo(): { version: string, buildTime: string } {
    return {
      version: this.getCurrentVersion(),
      buildTime: this.getBuildTime()
    };
  }
}

export default VersionService;