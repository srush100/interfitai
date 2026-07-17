import React, { useState } from 'react';
import {
  View, Text, StyleSheet, TextInput, TouchableOpacity,
  ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';

export default function ForgotPassword() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  const sendCode = async () => {
    setErr('');
    const e = email.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) { setErr('Please enter a valid email address'); return; }
    setLoading(true);
    try {
      await api.post('/auth/forgot-password', { email: e });
      setStep(2);
    } catch {
      setStep(2); // same UX regardless — never reveal if the account exists
    } finally { setLoading(false); }
  };

  const resetPassword = async () => {
    setErr('');
    if (code.trim().length !== 6) { setErr('Enter the 6-digit code from your email'); return; }
    if (newPassword.length < 8) { setErr('Password must be at least 8 characters'); return; }
    setLoading(true);
    try {
      await api.post('/auth/reset-password', {
        email: email.trim().toLowerCase(), code: code.trim(), new_password: newPassword,
      });
      Alert.alert('Password reset', 'You can now sign in with your new password.', [
        { text: 'Sign In', onPress: () => router.replace('/login') },
      ]);
    } catch (error: any) {
      setErr(error?.response?.data?.detail || 'Could not reset password. Please try again.');
    } finally { setLoading(false); }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <View style={styles.content}>
          <TouchableOpacity style={styles.back} onPress={() => (step === 2 ? setStep(1) : router.back())}>
            <Ionicons name="arrow-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <View style={styles.header}>
            <View style={styles.logoGlow}>
              <Image source={require('../assets/logo-icon-yellow.png')} style={styles.logo} resizeMode="contain" />
            </View>
            <Text style={styles.title}>{step === 1 ? 'Forgot Password' : 'Enter Code'}</Text>
            <Text style={styles.subtitle}>
              {step === 1
                ? "Enter your email and we'll send you a reset code."
                : `We sent a 6-digit code to ${email}. Enter it below with your new password.`}
            </Text>
          </View>
          {step === 1 ? (
            <View style={styles.form}>
              <View style={styles.inputContainer}>
                <Ionicons name="mail-outline" size={20} color={colors.textMuted} style={styles.inputIcon} />
                <TextInput
                  style={styles.input} placeholder="Enter your email" placeholderTextColor={colors.textMuted}
                  value={email} onChangeText={setEmail} keyboardType="email-address"
                  autoCapitalize="none" autoCorrect={false}
                />
              </View>
              {!!err && <Text style={styles.err}>{err}</Text>}
              <TouchableOpacity style={[styles.btn, loading && styles.btnDisabled]} onPress={sendCode} disabled={loading}>
                {loading ? <ActivityIndicator color="#000" /> : <Text style={styles.btnText}>Send Reset Code</Text>}
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.form}>
              <View style={styles.inputContainer}>
                <Ionicons name="keypad-outline" size={20} color={colors.textMuted} style={styles.inputIcon} />
                <TextInput
                  style={styles.input} placeholder="6-digit code" placeholderTextColor={colors.textMuted}
                  value={code} onChangeText={setCode} keyboardType="number-pad" maxLength={6}
                />
              </View>
              <View style={styles.inputContainer}>
                <Ionicons name="lock-closed-outline" size={20} color={colors.textMuted} style={styles.inputIcon} />
                <TextInput
                  style={styles.input} placeholder="New password (min 8 chars)" placeholderTextColor={colors.textMuted}
                  value={newPassword} onChangeText={setNewPassword} secureTextEntry={!showPw} autoCapitalize="none"
                />
                <TouchableOpacity onPress={() => setShowPw(!showPw)} style={styles.eye}>
                  <Ionicons name={showPw ? 'eye-off-outline' : 'eye-outline'} size={20} color={colors.textMuted} />
                </TouchableOpacity>
              </View>
              {!!err && <Text style={styles.err}>{err}</Text>}
              <TouchableOpacity style={[styles.btn, loading && styles.btnDisabled]} onPress={resetPassword} disabled={loading}>
                {loading ? <ActivityIndicator color="#000" /> : <Text style={styles.btnText}>Reset Password</Text>}
              </TouchableOpacity>
              <TouchableOpacity style={styles.resend} onPress={sendCode} disabled={loading}>
                <Text style={styles.resendText}>Didn't get it? Resend code</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { flex: 1, padding: 24, justifyContent: 'center' },
  back: { position: 'absolute', top: 8, left: 16, padding: 8 },
  header: { alignItems: 'center', marginBottom: 32 },
  logoGlow: { width: 90, height: 90, borderRadius: 45, backgroundColor: 'rgba(255,204,0,0.15)', borderWidth: 2, borderColor: 'rgba(255,204,0,0.3)', justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  logo: { width: 54, height: 54 },
  title: { fontSize: 26, fontWeight: '700', color: colors.text, marginBottom: 8 },
  subtitle: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 },
  form: {},
  inputContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.surface, borderRadius: 12, borderWidth: 1, borderColor: colors.border, marginBottom: 16 },
  inputIcon: { paddingLeft: 16 },
  eye: { paddingRight: 16, paddingVertical: 16 },
  input: { flex: 1, padding: 16, fontSize: 16, color: colors.text },
  err: { color: colors.error, fontSize: 14, marginBottom: 12 },
  btn: { backgroundColor: colors.primary, paddingVertical: 16, borderRadius: 12, alignItems: 'center' },
  btnDisabled: { opacity: 0.6 },
  btnText: { fontSize: 18, fontWeight: '600', color: '#000' },
  resend: { alignItems: 'center', paddingVertical: 16 },
  resendText: { fontSize: 14, color: colors.primary, fontWeight: '600' },
});
