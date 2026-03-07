import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Alert,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';

const ACTIVITY_LEVELS = [
  { id: 'sedentary', label: 'Sedentary', desc: 'Little to no exercise' },
  { id: 'light', label: 'Light', desc: '1-3 days/week' },
  { id: 'moderate', label: 'Moderate', desc: '3-5 days/week' },
  { id: 'active', label: 'Active', desc: '6-7 days/week' },
  { id: 'very_active', label: 'Very Active', desc: 'Athlete level' },
];

const GOALS = [
  { id: 'weight_loss', label: 'Lose Weight', icon: 'trending-down', desc: 'Caloric deficit for fat loss' },
  { id: 'maintenance', label: 'Maintain', icon: 'fitness', desc: 'Stay at current weight' },
  { id: 'muscle_building', label: 'Build Muscle', icon: 'barbell', desc: 'Caloric surplus for gains' },
];

const GENDERS = [
  { id: 'male', label: 'Male' },
  { id: 'female', label: 'Female' },
  { id: 'other', label: 'Other' },
];

export default function Onboarding() {
  const router = useRouter();
  const { createProfile, isLoading } = useUserStore();
  const [step, setStep] = useState(1);
  const [useMetric, setUseMetric] = useState(true); // Toggle for metric/imperial
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    weight: '',
    height: '',
    age: '',
    gender: 'male',
    activity_level: 'moderate',
    goal: 'muscle_building',
  });

  // Convert imperial to metric
  const convertToMetric = () => {
    let weightKg = parseFloat(formData.weight);
    let heightCm = parseFloat(formData.height);
    
    if (!useMetric) {
      // Convert lbs to kg
      weightKg = parseFloat(formData.weight) * 0.453592;
      // Convert inches to cm
      heightCm = parseFloat(formData.height) * 2.54;
    }
    
    return { weightKg, heightCm };
  };

  const handleNext = () => {
    if (step < 4) {
      setStep(step + 1);
    } else {
      handleSubmit();
    }
  };

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1);
    }
  };

  const handleSubmit = async () => {
    if (!formData.weight || !formData.height || !formData.age) {
      Alert.alert('Missing Info', 'Please fill in all required fields');
      return;
    }

    const { weightKg, heightCm } = convertToMetric();

    try {
      await createProfile({
        name: formData.name || 'Champion',
        email: formData.email,
        weight: Math.round(weightKg * 10) / 10,
        height: Math.round(heightCm * 10) / 10,
        age: parseInt(formData.age),
        gender: formData.gender,
        activity_level: formData.activity_level,
        goal: formData.goal,
      });
      router.replace('/(tabs)');
    } catch (error) {
      Alert.alert('Error', 'Failed to create profile. Please try again.');
    }
  };

  const renderStep1 = () => (
    <View style={styles.stepContainer}>
      {/* Logo and Welcome Section */}
      <View style={styles.welcomeHeader}>
        <View style={styles.logoGlow}>
          <Image
            source={require('../assets/logo-icon-yellow.png')}
            style={styles.welcomeLogo}
            resizeMode="contain"
          />
        </View>
        <Text style={styles.splashTitle}>
          <Text style={styles.splashWhite}>INTERFIT</Text>
          <Text style={styles.splashYellow}>AI</Text>
        </Text>
        <Text style={styles.splashSubtitle}>Your AI-Powered Fitness Journey{'\n'}Starts Here</Text>
      </View>
      
      <View style={styles.inputGroup}>
        <Text style={styles.label}>Your Name</Text>
        <TextInput
          style={styles.input}
          placeholder="Enter your name"
          placeholderTextColor={colors.textMuted}
          value={formData.name}
          onChangeText={(text) => setFormData({ ...formData, name: text })}
        />
      </View>

      <View style={styles.inputGroup}>
        <Text style={styles.label}>Email (optional)</Text>
        <TextInput
          style={styles.input}
          placeholder="Enter your email"
          placeholderTextColor={colors.textMuted}
          keyboardType="email-address"
          autoCapitalize="none"
          value={formData.email}
          onChangeText={(text) => setFormData({ ...formData, email: text })}
        />
      </View>
    </View>
  );

  const renderStep2 = () => (
    <View style={styles.stepContainer}>
      <Text style={styles.stepTitle}>Your Body Stats</Text>
      <Text style={styles.stepSubtitle}>We'll calculate your personalized macros using the Mifflin-St Jeor equation</Text>
      
      {/* Unit Toggle */}
      <View style={styles.unitToggle}>
        <TouchableOpacity
          style={[styles.unitBtn, useMetric && styles.unitBtnActive]}
          onPress={() => setUseMetric(true)}
        >
          <Text style={[styles.unitBtnText, useMetric && styles.unitBtnTextActive]}>
            Metric (kg/cm)
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.unitBtn, !useMetric && styles.unitBtnActive]}
          onPress={() => setUseMetric(false)}
        >
          <Text style={[styles.unitBtnText, !useMetric && styles.unitBtnTextActive]}>
            Imperial (lbs/in)
          </Text>
        </TouchableOpacity>
      </View>
      
      <View style={styles.row}>
        <View style={[styles.inputGroup, { flex: 1, marginRight: 8 }]}>
          <Text style={styles.label}>Weight ({useMetric ? 'kg' : 'lbs'})</Text>
          <TextInput
            style={styles.input}
            placeholder={useMetric ? '70' : '154'}
            placeholderTextColor={colors.textMuted}
            keyboardType="decimal-pad"
            value={formData.weight}
            onChangeText={(text) => setFormData({ ...formData, weight: text })}
          />
        </View>
        <View style={[styles.inputGroup, { flex: 1, marginLeft: 8 }]}>
          <Text style={styles.label}>Height ({useMetric ? 'cm' : 'inches'})</Text>
          <TextInput
            style={styles.input}
            placeholder={useMetric ? '175' : '69'}
            placeholderTextColor={colors.textMuted}
            keyboardType="decimal-pad"
            value={formData.height}
            onChangeText={(text) => setFormData({ ...formData, height: text })}
          />
        </View>
      </View>

      <View style={styles.row}>
        <View style={[styles.inputGroup, { flex: 1, marginRight: 8 }]}>
          <Text style={styles.label}>Age</Text>
          <TextInput
            style={styles.input}
            placeholder="25"
            placeholderTextColor={colors.textMuted}
            keyboardType="number-pad"
            value={formData.age}
            onChangeText={(text) => setFormData({ ...formData, age: text })}
          />
        </View>
        <View style={[styles.inputGroup, { flex: 1, marginLeft: 8 }]}>
          <Text style={styles.label}>Gender</Text>
          <View style={styles.genderContainer}>
            {GENDERS.map((g) => (
              <TouchableOpacity
                key={g.id}
                style={[
                  styles.genderBtn,
                  formData.gender === g.id && styles.genderBtnActive,
                ]}
                onPress={() => setFormData({ ...formData, gender: g.id })}
              >
                <Text
                  style={[
                    styles.genderText,
                    formData.gender === g.id && styles.genderTextActive,
                  ]}
                >
                  {g.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </View>
    </View>
  );

  const renderStep3 = () => (
    <View style={styles.stepContainer}>
      <Text style={styles.stepTitle}>Activity Level</Text>
      <Text style={styles.stepSubtitle}>How active are you on a weekly basis?</Text>
      
      {ACTIVITY_LEVELS.map((level) => (
        <TouchableOpacity
          key={level.id}
          style={[
            styles.optionCard,
            formData.activity_level === level.id && styles.optionCardActive,
          ]}
          onPress={() => setFormData({ ...formData, activity_level: level.id })}
        >
          <View>
            <Text
              style={[
                styles.optionTitle,
                formData.activity_level === level.id && styles.optionTitleActive,
              ]}
            >
              {level.label}
            </Text>
            <Text style={styles.optionDesc}>{level.desc}</Text>
          </View>
          {formData.activity_level === level.id && (
            <Ionicons name="checkmark-circle" size={24} color={colors.primary} />
          )}
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderStep4 = () => (
    <View style={styles.stepContainer}>
      <Text style={styles.stepTitle}>Your Goal</Text>
      <Text style={styles.stepSubtitle}>What do you want to achieve?</Text>
      
      {GOALS.map((goal) => (
        <TouchableOpacity
          key={goal.id}
          style={[
            styles.goalCard,
            formData.goal === goal.id && styles.goalCardActive,
          ]}
          onPress={() => setFormData({ ...formData, goal: goal.id })}
        >
          <View style={[styles.goalIcon, formData.goal === goal.id && styles.goalIconActive]}>
            <Ionicons
              name={goal.icon as any}
              size={28}
              color={formData.goal === goal.id ? colors.primary : colors.textSecondary}
            />
          </View>
          <View style={styles.goalContent}>
            <Text
              style={[
                styles.goalText,
                formData.goal === goal.id && styles.goalTextActive,
              ]}
            >
              {goal.label}
            </Text>
            <Text style={styles.goalDesc}>{goal.desc}</Text>
          </View>
          {formData.goal === goal.id && (
            <Ionicons name="checkmark-circle" size={24} color={colors.primary} />
          )}
        </TouchableOpacity>
      ))}
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {/* Progress */}
          <View style={styles.progressContainer}>
            {[1, 2, 3, 4].map((s) => (
              <View
                key={s}
                style={[
                  styles.progressDot,
                  s <= step && styles.progressDotActive,
                ]}
              />
            ))}
          </View>

          {step === 1 && renderStep1()}
          {step === 2 && renderStep2()}
          {step === 3 && renderStep3()}
          {step === 4 && renderStep4()}
        </ScrollView>

        {/* Navigation */}
        <View style={styles.navContainer}>
          {step > 1 && (
            <TouchableOpacity style={styles.backBtn} onPress={handleBack}>
              <Ionicons name="arrow-back" size={24} color={colors.text} />
            </TouchableOpacity>
          )}
          <TouchableOpacity
            style={[styles.nextBtn, isLoading && styles.btnDisabled]}
            onPress={handleNext}
            disabled={isLoading}
          >
            <Text style={styles.nextBtnText}>
              {step === 4 ? 'Calculate My Macros' : 'Continue'}
            </Text>
            <Ionicons name="arrow-forward" size={20} color={colors.textOnPrimary} />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    padding: 20,
  },
  progressContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: 32,
    gap: 8,
  },
  progressDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.surfaceLight,
  },
  progressDotActive: {
    backgroundColor: colors.primary,
    width: 24,
  },
  stepContainer: {
    flex: 1,
  },
  welcomeHeader: {
    alignItems: 'center',
    marginBottom: 36,
    paddingTop: 16,
  },
  logoGlow: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: colors.primary + '15',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 20,
    elevation: 10,
  },
  welcomeLogo: {
    width: 80,
    height: 80,
  },
  splashContainer: {
    alignItems: 'center',
    marginBottom: 32,
    paddingTop: 20,
  },
  splashTitle: {
    fontSize: 38,
    fontWeight: '800',
    letterSpacing: 2,
    marginBottom: 12,
  },
  splashWhite: {
    color: colors.text,
  },
  splashYellow: {
    color: colors.primary,
  },
  splashSubtitle: {
    fontSize: 15,
    color: colors.textSecondary,
    letterSpacing: 0.5,
    textAlign: 'center',
    lineHeight: 22,
  },
  logoContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  logoImage: {
    width: 100,
    height: 100,
  },
  brandName: {
    fontSize: 32,
    fontWeight: '800',
    color: colors.text,
    letterSpacing: 2,
    textAlign: 'center',
    marginBottom: 4,
  },
  brandAI: {
    color: colors.primary,
  },
  logoText: {
    fontSize: 36,
    fontWeight: '800',
    color: colors.text,
    letterSpacing: 3,
  },
  logoAI: {
    fontSize: 36,
    fontWeight: '800',
    color: colors.primary,
    letterSpacing: 3,
  },
  stepTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 8,
  },
  stepSubtitle: {
    fontSize: 15,
    color: colors.textSecondary,
    marginBottom: 28,
    textAlign: 'center',
    lineHeight: 22,
  },
  unitToggle: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 4,
    marginBottom: 24,
  },
  unitBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
  },
  unitBtnActive: {
    backgroundColor: colors.primary,
  },
  unitBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  unitBtnTextActive: {
    color: colors.textOnPrimary,
  },
  inputGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  row: {
    flexDirection: 'row',
  },
  genderContainer: {
    flexDirection: 'row',
    gap: 6,
  },
  genderBtn: {
    flex: 1,
    padding: 10,
    borderRadius: 8,
    backgroundColor: colors.surface,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  genderBtnActive: {
    backgroundColor: colors.primary + '20',
    borderColor: colors.primary,
  },
  genderText: {
    fontSize: 11,
    color: colors.textSecondary,
  },
  genderTextActive: {
    color: colors.primary,
    fontWeight: '600',
  },
  optionCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  optionCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  optionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  optionTitleActive: {
    color: colors.primary,
  },
  optionDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
  },
  goalCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 18,
    borderRadius: 16,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: colors.border,
  },
  goalCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  goalIcon: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: colors.surfaceLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  goalIconActive: {
    backgroundColor: colors.primary + '20',
  },
  goalContent: {
    flex: 1,
    marginLeft: 14,
  },
  goalText: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  goalTextActive: {
    color: colors.primary,
  },
  goalDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  navContainer: {
    flexDirection: 'row',
    padding: 20,
    gap: 12,
  },
  backBtn: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
  },
  nextBtn: {
    flex: 1,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
  },
  nextBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textOnPrimary,
  },
  btnDisabled: {
    opacity: 0.5,
  },
});
