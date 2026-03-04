import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';

const GOALS = [
  { id: 'build_muscle', label: 'Build Muscle', icon: 'barbell' },
  { id: 'lose_fat', label: 'Lose Fat', icon: 'flame' },
  { id: 'general_fitness', label: 'General Fitness', icon: 'fitness' },
];

const FOCUS_AREAS = [
  { id: 'full_body', label: 'Full Body' },
  { id: 'back', label: 'Back' },
  { id: 'chest', label: 'Chest' },
  { id: 'legs', label: 'Legs' },
  { id: 'glutes', label: 'Glutes' },
  { id: 'arms', label: 'Arms' },
  { id: 'shoulders', label: 'Shoulders' },
  { id: 'core', label: 'Core' },
];

const EQUIPMENT = [
  { id: 'full_gym', label: 'Full Gym' },
  { id: 'barbells', label: 'Barbells' },
  { id: 'dumbbells', label: 'Dumbbells' },
  { id: 'bodyweight', label: 'Body Weight' },
  { id: 'kettlebells', label: 'Kettlebells' },
  { id: 'machines', label: 'Machines' },
  { id: 'cables', label: 'Cables' },
];

const DAYS_OPTIONS = [2, 3, 4, 5, 6];

export default function WorkoutQuestionnaire() {
  const router = useRouter();
  const { profile } = useUserStore();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    goal: 'build_muscle',
    focus_areas: ['full_body'] as string[],
    equipment: ['full_gym'] as string[],
    injuries: '',
    days_per_week: 4,
  });

  const toggleSelection = (field: 'focus_areas' | 'equipment', value: string) => {
    const current = formData[field];
    if (current.includes(value)) {
      if (current.length > 1) {
        setFormData({ ...formData, [field]: current.filter((v) => v !== value) });
      }
    } else {
      setFormData({ ...formData, [field]: [...current, value] });
    }
  };

  const handleGenerate = async () => {
    if (!profile?.id) {
      Alert.alert('Error', 'Please complete your profile first');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/workouts/generate', {
        user_id: profile.id,
        goal: formData.goal,
        focus_areas: formData.focus_areas,
        equipment: formData.equipment,
        injuries: formData.injuries || null,
        days_per_week: formData.days_per_week,
      });

      router.replace(`/workout-detail?id=${response.data.id}`);
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to generate workout. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const renderStep1 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Choose Training Goal</Text>
      <Text style={styles.stepSubtitle}>What do you want to achieve?</Text>
      
      {GOALS.map((goal) => (
        <TouchableOpacity
          key={goal.id}
          style={[styles.goalCard, formData.goal === goal.id && styles.goalCardActive]}
          onPress={() => setFormData({ ...formData, goal: goal.id })}
        >
          <Ionicons
            name={goal.icon as any}
            size={28}
            color={formData.goal === goal.id ? colors.primary : colors.textSecondary}
          />
          <Text style={[styles.goalText, formData.goal === goal.id && styles.goalTextActive]}>
            {goal.label}
          </Text>
          {formData.goal === goal.id && (
            <Ionicons name="checkmark-circle" size={24} color={colors.primary} />
          )}
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderStep2 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Choose Focus Areas</Text>
      <Text style={styles.stepSubtitle}>Select one or more muscle groups</Text>
      
      <View style={styles.chipContainer}>
        {FOCUS_AREAS.map((area) => (
          <TouchableOpacity
            key={area.id}
            style={[styles.chip, formData.focus_areas.includes(area.id) && styles.chipActive]}
            onPress={() => toggleSelection('focus_areas', area.id)}
          >
            <Text style={[styles.chipText, formData.focus_areas.includes(area.id) && styles.chipTextActive]}>
              {area.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  const renderStep3 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Choose Equipment</Text>
      <Text style={styles.stepSubtitle}>What equipment do you have access to?</Text>
      
      <View style={styles.chipContainer}>
        {EQUIPMENT.map((eq) => (
          <TouchableOpacity
            key={eq.id}
            style={[styles.chip, formData.equipment.includes(eq.id) && styles.chipActive]}
            onPress={() => toggleSelection('equipment', eq.id)}
          >
            <Text style={[styles.chipText, formData.equipment.includes(eq.id) && styles.chipTextActive]}>
              {eq.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  const renderStep4 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Do You Have Injuries?</Text>
      <Text style={styles.stepSubtitle}>Let us know so we can adjust your program</Text>
      
      <TextInput
        style={styles.textInput}
        placeholder="e.g., Lower back pain, knee issues, or 'None'"
        placeholderTextColor={colors.textMuted}
        value={formData.injuries}
        onChangeText={(text) => setFormData({ ...formData, injuries: text })}
        multiline
      />

      <Text style={[styles.stepTitle, { marginTop: 32 }]}>Days Per Week</Text>
      <Text style={styles.stepSubtitle}>How many days can you train?</Text>
      
      <View style={styles.daysContainer}>
        {DAYS_OPTIONS.map((days) => (
          <TouchableOpacity
            key={days}
            style={[styles.dayBtn, formData.days_per_week === days && styles.dayBtnActive]}
            onPress={() => setFormData({ ...formData, days_per_week: days })}
          >
            <Text style={[styles.dayBtnText, formData.days_per_week === days && styles.dayBtnTextActive]}>
              {days}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="close" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Create Workout</Text>
        <View style={styles.backBtn} />
      </View>

      {/* Progress */}
      <View style={styles.progressContainer}>
        {[1, 2, 3, 4].map((s) => (
          <View key={s} style={[styles.progressDot, s <= step && styles.progressDotActive]} />
        ))}
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
        {step === 4 && renderStep4()}
      </ScrollView>

      {/* Navigation */}
      <View style={styles.navContainer}>
        {step > 1 && (
          <TouchableOpacity style={styles.navBackBtn} onPress={() => setStep(step - 1)}>
            <Ionicons name="arrow-back" size={24} color={colors.text} />
          </TouchableOpacity>
        )}
        <TouchableOpacity
          style={[styles.navNextBtn, loading && styles.btnDisabled]}
          onPress={step < 4 ? () => setStep(step + 1) : handleGenerate}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator size="small" color={colors.background} />
          ) : (
            <>
              <Text style={styles.navNextText}>
                {step < 4 ? 'Continue' : 'Generate Workout'}
              </Text>
              <Ionicons name="arrow-forward" size={20} color={colors.background} />
            </>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  progressContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    paddingBottom: 16,
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
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  stepContent: {
    flex: 1,
  },
  stepTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 8,
  },
  stepSubtitle: {
    fontSize: 15,
    color: colors.textSecondary,
    marginBottom: 24,
  },
  goalCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 18,
    borderRadius: 14,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: colors.border,
    gap: 14,
  },
  goalCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  goalText: {
    flex: 1,
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  goalTextActive: {
    color: colors.primary,
  },
  chipContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  chip: {
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: 25,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: {
    backgroundColor: colors.primary + '20',
    borderColor: colors.primary,
  },
  chipText: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  chipTextActive: {
    color: colors.primary,
  },
  textInput: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 80,
    textAlignVertical: 'top',
  },
  daysContainer: {
    flexDirection: 'row',
    gap: 12,
  },
  dayBtn: {
    flex: 1,
    padding: 16,
    borderRadius: 12,
    backgroundColor: colors.surface,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  dayBtnActive: {
    backgroundColor: colors.primary + '20',
    borderColor: colors.primary,
  },
  dayBtnText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  dayBtnTextActive: {
    color: colors.primary,
  },
  navContainer: {
    flexDirection: 'row',
    padding: 20,
    gap: 12,
  },
  navBackBtn: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
  },
  navNextBtn: {
    flex: 1,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
  },
  navNextText: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.background,
  },
  btnDisabled: {
    opacity: 0.7,
  },
});