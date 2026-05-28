import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.coherence.coach',
  appName: 'CoherenceCoach',
  webDir: 'dist',
  server: {
    url: 'http://192.168.1.103:8001',
    cleartext: true,
  },
  android: {
    allowMixedContent: true,
  },
};

export default config;
