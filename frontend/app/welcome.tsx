import React from 'react';
import { View, Text, StyleSheet, Image, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { colors } from '../src/theme/colors';

export default function WelcomeScreen() {
  const router = useRouter();

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        <View style={styles.header}>
          <View style={styles.logoGlow}>
            <Image
              source={require('../assets/logo-icon-yellow.png')}
              style={styles.logo}
              resizeMode="contain"
            />
          </View>
          <View style={styles.titleContainer}>
            <Text style={styles.title}>INTERFIT</Text>
            <Text style={styles.titleAI}>AI</Text>
          </View>
          <Text style={styles.tagline}>Your AI-Powered Fitness Companion</Text>
        </View>

        <View style={styles.actions}>
          <TouchableOpacity
            style={styles.primaryBtn}
            onPress={() => router.push('/onboarding')}
            activeOpacity={0.85}
          >
            <Text style={styles.primaryBtnText}>Get Started</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.secondaryBtn}
            onPress={() => router.push('/login')}
            activeOpacity={0.85}
          >
            <Text style={styles.secondaryBtnText}>Sign In</Text>
          </TouchableOpacity>

          <Text style={styles.helperText}>
            New here? Tap Get Started. Already have an account? Sign In.
          </Text>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { flex: 1, padding: 24, justifyContent: 'space-between' },
  header: { alignItems: 'center', marginTop: 80 },
  logoGlow: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: 'rgba(255, 204, 0, 0.15)',
    borderWidth: 2,
    borderColor: 'rgba(255, 204, 0, 0.3)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  logo: { width: 70, height: 70 },
  titleContainer: { flexDirection: 'row', alignItems: 'baseline' },
  title: { fontSize: 42, fontWeight: '800', color: colors.text, letterSpacing: 2 },
  titleAI: { fontSize: 42, fontWeight: '800', color: colors.primary, letterSpacing: 2 },
  tagline: { fontSize: 16, color: colors.textSecondary, marginTop: 12, letterSpacing: 1, textAlign: 'center' },
  actions: { marginBottom: 40, paddingTop: 40 },
  primaryBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 16,
  },
  primaryBtnText: { fontSize: 18, fontWeight: '700', color: '#000' },
  secondaryBtn: {
    borderWidth: 2,
    borderColor: colors.primary,
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  secondaryBtnText: { fontSize: 16, fontWeight: '600', color: colors.primary },
  helperText: { fontSize: 13, color: colors.textMuted, textAlign: 'center', lineHeight: 20, marginTop: 20 },
});
