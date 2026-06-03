import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';

const CREDENTIALS_KEY = 'interfitai_credentials';

export default function LoginScreen() {
  const router = useRouter();
  const { loginWithPassword, isLoading, error } = useUserStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [biometricAvailable, setBiometricAvailable] = useState(false);
  const [hasSavedCredentials, setHasSavedCredentials] = useState(false);
  const [validationError, setValidationError] = useState('');

  useEffect(() => {
    checkBiometrics();
  }, []);

  const checkBiometrics = async () => {
    try {
      const compatible = await LocalAuthentication.hasHardwareAsync();
      const enrolled = await LocalAuthentication.isEnrolledAsync();
      const available = compatible && enrolled;
      setBiometricAvailable(available);

      if (available) {
        const stored = await SecureStore.getItemAsync(CREDENTIALS_KEY);
        if (stored) {
          setHasSavedCredentials(true);
          const { email: savedEmail } = JSON.parse(stored);
          setEmail(savedEmail);
        }
      }
    } catch (e) {
      console.log('Biometrics check:', e);
    }
  };

  const handleBiometricLogin = async () => {
    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Sign in to InterFitAI',
        cancelLabel: 'Use Password',
        disableDeviceFallback: false,
      });

      if (result.success) {
        const stored = await SecureStore.getItemAsync(CREDENTIALS_KEY);
        if (stored) {
          const { email: savedEmail, password: savedPassword } = JSON.parse(stored);
          const success = await loginWithPassword(savedEmail, savedPassword);
          if (success) {
            router.replace('/(tabs)');
          } else {
            Alert.alert('Login Failed', 'Your saved credentials may have changed. Please sign in with your password.');
            await SecureStore.deleteItemAsync(CREDENTIALS_KEY);
            setHasSavedCredentials(false);
          }
        }
      }
    } catch (e) {
      console.log('Biometric login error:', e);
    }
  };

  const handleLogin = async () => {
    setValidationError('');
    if (!email.trim()) {
      setValidationError('Please enter your email address');
      return;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      setValidationError('Please enter a valid email address');
      return;
    }
    if (!password) {
      setValidationError('Please enter your password');
      return;
    }

    const success = await loginWithPassword(email.trim().toLowerCase(), password);

    if (success) {
      if (biometricAvailable) {
        try {
          await SecureStore.setItemAsync(
            CREDENTIALS_KEY,
            JSON.stringify({ email: email.trim().toLowerCase(), password })
          );
        } catch (e) {
          console.log('Could not save credentials for biometric login');
        }
      }
      router.replace('/(tabs)');
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <View style={styles.content}>
          <View style={styles.header}>
            <View style={styles.logoGlow}>
              <Image
                source={require('../assets/logo-icon-yellow.png')}
                style={styles.welcomeLogo}
                resizeMode="contain"
              />
            </View>
            <View style={styles.titleContainer}>
              <Text style={styles.title}>INTERFIT</Text>
              <Text style={styles.titleAI}>AI</Text>
            </View>
            <Text style={styles.subtitle}>Sign in to your account</Text>
          </View>

          {biometricAvailable && hasSavedCredentials && (
            <TouchableOpacity style={styles.biometricBtn} onPress={handleBiometricLogin}>
              <Ionicons
                name={Platform.OS === 'ios' ? 'scan' : 'finger-print'}
                size={32}
                color={colors.primary}
              />
              <Text style={styles.biometricText}>
                {Platform.OS === 'ios' ? 'Sign in with Face ID' : 'Sign in with Fingerprint'}
              </Text>
            </TouchableOpacity>
          )}

          <View style={styles.form}>
            <Text style={styles.label}>Email Address</Text>
            <View style={styles.inputContainer}>
              <Ionicons name="mail-outline" size={20} color={colors.textMuted} style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="Enter your email"
                placeholderTextColor={colors.textMuted}
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                autoComplete="email"
              />
            </View>

            <Text style={styles.label}>Password</Text>
            <View style={styles.inputContainer}>
              <Ionicons name="lock-closed-outline" size={20} color={colors.textMuted} style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="Enter your password"
                placeholderTextColor={colors.textMuted}
                value={password}
                onChangeText={setPassword}
                secureTextEntry={!showPassword}
                autoCapitalize="none"
                autoComplete="password"
              />
              <TouchableOpacity
                onPress={() => setShowPassword(!showPassword)}
                style={styles.eyeIcon}
              >
                <Ionicons
                  name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                  size={20}
                  color={colors.textMuted}
                />
              </TouchableOpacity>
            </View>

            {(validationError || error) && (
              <View style={styles.errorContainer}>
                <Ionicons name="alert-circle" size={16} color={colors.error} />
                <Text style={styles.errorText}>{validationError || error}</Text>
              </View>
            )}

            <TouchableOpacity
              style={[styles.loginBtn, isLoading && styles.loginBtnDisabled]}
              onPress={handleLogin}
              disabled={isLoading}
            >
              {isLoading ? (
                <ActivityIndicator color="#000" />
              ) : (
                <Text style={styles.loginBtnText}>Sign In</Text>
              )}
            </TouchableOpacity>
          </View>

          <View style={styles.divider}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>or</Text>
            <View style={styles.dividerLine} />
          </View>

          <TouchableOpacity style={styles.createAccountBtn} onPress={() => router.push('/onboarding')}>
            <Text style={styles.createAccountText}>Create New Account</Text>
          </TouchableOpacity>

          <Text style={styles.infoText}>
            Sign in with the email and password you used when you created your account.
          </Text>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  keyboardView: { flex: 1 },
  content: { flex: 1, padding: 24, justifyContent: 'center' },
  header: { alignItems: 'center', marginBottom: 32 },
  logoGlow: { width: 100, height: 100, borderRadius: 50, backgroundColor: 'rgba(255, 204, 0, 0.15)', borderWidth: 2, borderColor: 'rgba(255, 204, 0, 0.3)', justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  welcomeLogo: { width: 60, height: 60 },
  titleContainer: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  title: { fontSize: 32, fontWeight: '700', color: colors.text, letterSpacing: 2 },
  titleAI: { fontSize: 32, fontWeight: '700', color: colors.primary, letterSpacing: 2 },
  subtitle: { fontSize: 16, color: colors.textSecondary },
  biometricBtn: { alignItems: 'center', justifyContent: 'center', paddingVertical: 20, marginBottom: 16, backgroundColor: colors.surface, borderRadius: 16, borderWidth: 1, borderColor: colors.primary + '40', gap: 8 },
  biometricText: { fontSize: 15, fontWeight: '600', color: colors.primary },
  form: { marginBottom: 24 },
  label: { fontSize: 14, fontWeight: '600', color: colors.text, marginBottom: 8 },
  inputContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.surface, borderRadius: 12, borderWidth: 1, borderColor: colors.border, marginBottom: 16 },
  inputIcon: { paddingLeft: 16 },
  eyeIcon: { paddingRight: 16, paddingVertical: 16 },
  input: { flex: 1, padding: 16, fontSize: 16, color: colors.text },
  errorContainer: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 16 },
  errorText: { fontSize: 14, color: colors.error, flex: 1 },
  loginBtn: { backgroundColor: colors.primary, paddingVertical: 16, borderRadius: 12, alignItems: 'center' },
  loginBtnDisabled: { opacity: 0.6 },
  loginBtnText: { fontSize: 18, fontWeight: '600', color: '#000' },
  divider: { flexDirection: 'row', alignItems: 'center', marginVertical: 24 },
  dividerLine: { flex: 1, height: 1, backgroundColor: colors.border },
  dividerText: { marginHorizontal: 16, fontSize: 14, color: colors.textMuted },
  createAccountBtn: { borderWidth: 2, borderColor: colors.primary, paddingVertical: 16, borderRadius: 12, alignItems: 'center', marginBottom: 24 },
  createAccountText: { fontSize: 16, fontWeight: '600', color: colors.primary },
  infoText: { fontSize: 13, color: colors.textMuted, textAlign: 'center', lineHeight: 20 },
});
