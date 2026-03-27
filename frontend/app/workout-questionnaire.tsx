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
import usePremium from '../src/hooks/usePremium';

// Step 1: Goals
const GOALS = [
  { id: 'build_muscle',        label: 'Build Muscle',          icon: 'barbell',       desc: 'Maximize muscle growth & size' },
  { id: 'lose_fat',            label: 'Lose Fat',               icon: 'flame',         desc: 'Burn fat while preserving muscle' },
  { id: 'body_recomp',         label: 'Body Recomposition',     icon: 'body',          desc: 'Build muscle & lose fat together' },
  { id: 'strength',            label: 'Build Strength',         icon: 'trophy',        desc: 'Increase power & max lifts' },
  { id: 'general_fitness',     label: 'General Fitness',        icon: 'fitness',       desc: 'Overall health & conditioning' },
  { id: 'athletic_performance',label: 'Athletic Performance',   icon: 'flash',         desc: 'Power, speed & athletic output' },
];

// Step 2: Training Style
const TRAINING_STYLES = [
  { id: 'weights', label: 'Weights', icon: 'barbell-outline', desc: 'Traditional gym equipment' },
  { id: 'calisthenics', label: 'Calisthenics', icon: 'body-outline', desc: 'Bodyweight focused training' },
  { id: 'hybrid', label: 'Hybrid', icon: 'git-merge-outline', desc: 'Mix of weights & bodyweight' },
  { id: 'functional', label: 'Functional', icon: 'flash-outline', desc: 'Athletic & movement based' },
];

// Step 3: Focus Areas
const FOCUS_AREAS = [
  { id: 'full_body', label: 'Full Body', featured: true },
  { id: 'upper_body', label: 'Upper Body' },
  { id: 'lower_body', label: 'Lower Body' },
  { id: 'chest', label: 'Chest' },
  { id: 'back', label: 'Back' },
  { id: 'shoulders', label: 'Shoulders' },
  { id: 'arms', label: 'Arms' },
  { id: 'legs', label: 'Legs' },
  { id: 'glutes', label: 'Glutes' },
  { id: 'core', label: 'Core' },
];

// Step 4: Equipment
const EQUIPMENT = [
  { id: 'full_gym', label: 'Full Gym' },
  { id: 'barbells', label: 'Barbells' },
  { id: 'dumbbells', label: 'Dumbbells' },
  { id: 'bodyweight', label: 'Body Weight' },
  { id: 'kettlebells', label: 'Kettlebells' },
  { id: 'machines', label: 'Machines' },
  { id: 'cables', label: 'Cables' },
  { id: 'resistance_bands', label: 'Bands' },
];

// Step 5: Duration & Days
const DURATIONS = [
  { id: 30, label: '30 min', desc: 'Quick & efficient' },
  { id: 45, label: '45 min', desc: 'Balanced workout' },
  { id: 60, label: '60 min', desc: 'Full session' },
  { id: 90, label: '90 min', desc: 'Extended training' },
];

const DAYS_OPTIONS = [2, 3, 4, 5, 6];

const FITNESS_LEVELS = [
  { id: 'beginner', label: 'Beginner', icon: 'leaf', desc: 'New to fitness or returning' },
  { id: 'intermediate', label: 'Intermediate', icon: 'trending-up', desc: '6+ months training' },
  { id: 'advanced', label: 'Advanced', icon: 'flash', desc: '2+ years serious training' },
];

// Step 6: Preferred Split
const WORKOUT_SPLITS = [
  { id: 'ai_choose', label: 'Let AI Choose', icon: 'sparkles', desc: 'Best split for your goals' },
  { id: 'full_body', label: 'Full Body', icon: 'body', desc: 'Train everything each session' },
  { id: 'upper_lower', label: 'Upper / Lower', icon: 'swap-vertical', desc: 'Alternate upper & lower' },
  { id: 'push_pull_legs', label: 'Push Pull Legs', icon: 'git-branch', desc: 'Classic 3-day rotation' },
  { id: 'bro_split', label: 'Bro Split', icon: 'calendar', desc: 'One muscle group per day' },
];

export default function WorkoutQuestionnaire() {
  const router = useRouter();
  const { profile } = useUserStore();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [checkingSubscription, setCheckingSubscription] = useState(false);
  const [formData, setFormData] = useState({
    goal: 'build_muscle',
    training_style: 'weights',
    focus_areas: ['full_body'] as string[],
    equipment: ['full_gym'] as string[],
    days_per_week: 4,
    duration_minutes: 60,
    fitness_level: 'intermediate',
    preferred_split: 'ai_choose',
    injuries: '',
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

    // Check subscription status before generating
    setCheckingSubscription(true);
    try {
      const subResponse = await api.get(`/subscription/check/${profile.id}`);
      if (!subResponse.data.has_access) {
        setCheckingSubscription(false);
        Alert.alert(
          'Subscription Required',
          'Start your free trial to generate personalized AI workouts!',
          [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Start Free Trial', onPress: () => router.push('/subscription') },
          ]
        );
        return;
      }
    } catch (error) {
      console.log('Subscription check error:', error);
    } finally {
      setCheckingSubscription(false);
    }

    setLoading(true);
    try {
      const response = await api.post('/workouts/generate', {
        user_id: profile.id,
        goal: formData.goal,
        training_style: formData.training_style,
        focus_areas: formData.focus_areas.slice(0, 1),             // first = primary
        secondary_focus_areas: formData.focus_areas.slice(1),      // rest = secondary
        equipment: formData.equipment,
        injuries: formData.injuries
          ? formData.injuries.split(',').map((s) => s.trim()).filter(Boolean)
          : null,
        days_per_week: formData.days_per_week,
        duration_minutes: formData.duration_minutes,
        fitness_level: formData.fitness_level,
        preferred_split: formData.preferred_split,
      });

      router.replace(`/workout-detail?id=${response.data.id}`);
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      const message = Array.isArray(detail)
        ? 'Please check your inputs and try again.'
        : (typeof detail === 'string' ? detail : 'Failed to generate workout. Please try again.');
      Alert.alert('Error', message);
    } finally {
      setLoading(false);
    }
  };

  // Step 1: Goal Selection
  const renderStep1 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>What's your main goal?</Text>
      <Text style={styles.stepSubtitle}>This will shape your entire program</Text>
      
      {GOALS.map((goal) => (
        <TouchableOpacity
          key={goal.id}
          style={[styles.optionCard, formData.goal === goal.id && styles.optionCardActive]}
          onPress={() => setFormData({ ...formData, goal: goal.id })}
        >
          <View style={[styles.optionIcon, formData.goal === goal.id && styles.optionIconActive]}>
            <Ionicons
              name={goal.icon as any}
              size={24}
              color={formData.goal === goal.id ? colors.background : colors.primary}
            />
          </View>
          <View style={styles.optionContent}>
            <Text style={[styles.optionLabel, formData.goal === goal.id && styles.optionLabelActive]}>
              {goal.label}
            </Text>
            <Text style={styles.optionDesc}>{goal.desc}</Text>
          </View>
          {formData.goal === goal.id && (
            <Ionicons name="checkmark-circle" size={24} color={colors.primary} />
          )}
        </TouchableOpacity>
      ))}
    </View>
  );

  // Step 2: Training Style
  const renderStep2 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>How do you want to train?</Text>
      <Text style={styles.stepSubtitle}>Choose your preferred training style</Text>
      
      <View style={styles.styleGrid}>
        {TRAINING_STYLES.map((style) => (
          <TouchableOpacity
            key={style.id}
            style={[styles.styleCard, formData.training_style === style.id && styles.styleCardActive]}
            onPress={() => setFormData({ ...formData, training_style: style.id })}
          >
            <View style={[styles.styleIconWrap, formData.training_style === style.id && styles.styleIconWrapActive]}>
              <Ionicons
                name={style.icon as any}
                size={28}
                color={formData.training_style === style.id ? colors.background : colors.primary}
              />
            </View>
            <Text style={[styles.styleLabel, formData.training_style === style.id && styles.styleLabelActive]}>
              {style.label}
            </Text>
            <Text style={styles.styleDesc}>{style.desc}</Text>
            {formData.training_style === style.id && (
              <View style={styles.checkBadge}>
                <Ionicons name="checkmark" size={14} color={colors.background} />
              </View>
            )}
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  // Step 3: Focus Areas
  const renderStep3 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>What do you want to focus on?</Text>
      <Text style={styles.stepSubtitle}>
        First selection = primary focus. Add more for secondary emphasis.
      </Text>

      {formData.focus_areas.length > 0 && (
        <View style={styles.focusBadgeRow}>
          <View style={styles.focusBadgePrimary}>
            <Ionicons name="star" size={12} color={colors.background} />
            <Text style={styles.focusBadgePrimaryText}>
              Primary: {FOCUS_AREAS.find(f => f.id === formData.focus_areas[0])?.label}
            </Text>
          </View>
          {formData.focus_areas.length > 1 && (
            <View style={styles.focusBadgeSecondary}>
              <Text style={styles.focusBadgeSecondaryText}>
                +{formData.focus_areas.length - 1} secondary
              </Text>
            </View>
          )}
        </View>
      )}

      <View style={styles.chipContainer}>
        {FOCUS_AREAS.map((area, idx) => {
          const isSelected = formData.focus_areas.includes(area.id);
          const isPrimary  = formData.focus_areas[0] === area.id;
          return (
            <TouchableOpacity
              key={area.id}
              style={[
                styles.chip,
                isSelected && styles.chipActive,
                isPrimary && styles.chipPrimary,
                area.featured && !isSelected && styles.chipFeatured,
              ]}
              onPress={() => toggleSelection('focus_areas', area.id)}
            >
              {isPrimary && (
                <Ionicons name="star" size={13} color={colors.primary} style={styles.chipCheck} />
              )}
              {isSelected && !isPrimary && (
                <Ionicons name="checkmark" size={13} color={colors.primary} style={styles.chipCheck} />
              )}
              <Text style={[styles.chipText, isSelected && styles.chipTextActive]}>
                {area.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );

  // Step 4: Equipment
  const renderStep4 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>What equipment do you have?</Text>
      <Text style={styles.stepSubtitle}>Select all that apply</Text>
      
      <View style={styles.chipContainer}>
        {EQUIPMENT.map((eq) => (
          <TouchableOpacity
            key={eq.id}
            style={[styles.chip, formData.equipment.includes(eq.id) && styles.chipActive]}
            onPress={() => toggleSelection('equipment', eq.id)}
          >
            {formData.equipment.includes(eq.id) && (
              <Ionicons name="checkmark" size={16} color={colors.primary} style={styles.chipCheck} />
            )}
            <Text style={[styles.chipText, formData.equipment.includes(eq.id) && styles.chipTextActive]}>
              {eq.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  // Step 5: Duration, Days, Level
  const renderStep5 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>How long per workout?</Text>
      <Text style={styles.stepSubtitle}>Choose your session duration</Text>
      
      <View style={styles.durationGrid}>
        {DURATIONS.map((dur) => (
          <TouchableOpacity
            key={dur.id}
            style={[styles.durationCard, formData.duration_minutes === dur.id && styles.durationCardActive]}
            onPress={() => setFormData({ ...formData, duration_minutes: dur.id })}
          >
            <Text style={[styles.durationValue, formData.duration_minutes === dur.id && styles.durationValueActive]}>
              {dur.label}
            </Text>
            <Text style={styles.durationDesc}>{dur.desc}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={[styles.stepTitle, { marginTop: 28 }]}>How many days per week?</Text>
      <Text style={styles.stepSubtitle}>Training frequency</Text>
      
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

      <Text style={[styles.stepTitle, { marginTop: 28 }]}>Your fitness level?</Text>
      <Text style={styles.stepSubtitle}>Be honest for best results</Text>
      
      <View style={styles.levelContainer}>
        {FITNESS_LEVELS.map((level) => (
          <TouchableOpacity
            key={level.id}
            style={[styles.levelCard, formData.fitness_level === level.id && styles.levelCardActive]}
            onPress={() => setFormData({ ...formData, fitness_level: level.id })}
          >
            <View style={[styles.levelIcon, formData.fitness_level === level.id && styles.levelIconActive]}>
              <Ionicons 
                name={level.icon as any} 
                size={20} 
                color={formData.fitness_level === level.id ? colors.background : colors.primary} 
              />
            </View>
            <View style={styles.levelContent}>
              <Text style={[styles.levelLabel, formData.fitness_level === level.id && styles.levelLabelActive]}>
                {level.label}
              </Text>
              <Text style={styles.levelDesc}>{level.desc}</Text>
            </View>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  // Step 6: Preferred Split
  const renderStep6 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Preferred workout split?</Text>
      <Text style={styles.stepSubtitle}>How do you want your program structured</Text>
      
      {WORKOUT_SPLITS.map((split) => (
        <TouchableOpacity
          key={split.id}
          style={[styles.optionCard, formData.preferred_split === split.id && styles.optionCardActive]}
          onPress={() => setFormData({ ...formData, preferred_split: split.id })}
        >
          <View style={[styles.optionIcon, formData.preferred_split === split.id && styles.optionIconActive]}>
            <Ionicons
              name={split.icon as any}
              size={22}
              color={formData.preferred_split === split.id ? colors.background : colors.primary}
            />
          </View>
          <View style={styles.optionContent}>
            <Text style={[styles.optionLabel, formData.preferred_split === split.id && styles.optionLabelActive]}>
              {split.label}
            </Text>
            <Text style={styles.optionDesc}>{split.desc}</Text>
          </View>
          {formData.preferred_split === split.id && (
            <Ionicons name="checkmark-circle" size={24} color={colors.primary} />
          )}
        </TouchableOpacity>
      ))}
    </View>
  );

  // Step 7: Injuries & Summary
  const renderStep7 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Any injuries or limitations?</Text>
      <Text style={styles.stepSubtitle}>We'll adjust exercises accordingly</Text>
      
      <TextInput
        style={styles.textInput}
        placeholder="e.g., Lower back pain, knee issues, or 'None'"
        placeholderTextColor={colors.textMuted}
        value={formData.injuries}
        onChangeText={(text) => setFormData({ ...formData, injuries: text })}
        multiline
      />

      {/* Enhanced Summary Card */}
      <View style={styles.summaryCard}>
        <Text style={styles.summaryTitle}>Your Custom Program</Text>
        
        <View style={styles.summaryRow}>
          <View style={styles.summaryIcon}>
            <Ionicons name="flag" size={16} color={colors.primary} />
          </View>
          <View style={styles.summaryContent}>
            <Text style={styles.summaryLabel}>Goal</Text>
            <Text style={styles.summaryValue}>
              {GOALS.find(g => g.id === formData.goal)?.label}
            </Text>
          </View>
        </View>

        <View style={styles.summaryRow}>
          <View style={styles.summaryIcon}>
            <Ionicons name="barbell-outline" size={16} color={colors.primary} />
          </View>
          <View style={styles.summaryContent}>
            <Text style={styles.summaryLabel}>Style</Text>
            <Text style={styles.summaryValue}>
              {TRAINING_STYLES.find(s => s.id === formData.training_style)?.label}
            </Text>
          </View>
        </View>

        <View style={styles.summaryRow}>
          <View style={styles.summaryIcon}>
            <Ionicons name="git-branch" size={16} color={colors.primary} />
          </View>
          <View style={styles.summaryContent}>
            <Text style={styles.summaryLabel}>Split</Text>
            <Text style={styles.summaryValue}>
              {WORKOUT_SPLITS.find(s => s.id === formData.preferred_split)?.label}
            </Text>
          </View>
        </View>

        <View style={styles.summaryRow}>
          <View style={styles.summaryIcon}>
            <Ionicons name="time" size={16} color={colors.primary} />
          </View>
          <View style={styles.summaryContent}>
            <Text style={styles.summaryLabel}>Schedule</Text>
            <Text style={styles.summaryValue}>
              {formData.duration_minutes} min, {formData.days_per_week}x/week
            </Text>
          </View>
        </View>

        <View style={styles.summaryRow}>
          <View style={styles.summaryIcon}>
            <Ionicons name="trending-up" size={16} color={colors.primary} />
          </View>
          <View style={styles.summaryContent}>
            <Text style={styles.summaryLabel}>Level</Text>
            <Text style={styles.summaryValue}>
              {FITNESS_LEVELS.find(l => l.id === formData.fitness_level)?.label}
            </Text>
          </View>
        </View>

        <View style={styles.summaryRow}>
          <View style={styles.summaryIcon}>
            <Ionicons name="body" size={16} color={colors.primary} />
          </View>
          <View style={styles.summaryContent}>
            <Text style={styles.summaryLabel}>Focus</Text>
            <Text style={styles.summaryValue}>
              {formData.focus_areas.slice(0, 3).map(a => 
                FOCUS_AREAS.find(f => f.id === a)?.label
              ).join(', ')}
              {formData.focus_areas.length > 3 && ` +${formData.focus_areas.length - 3}`}
            </Text>
          </View>
        </View>
      </View>
    </View>
  );

  const totalSteps = 7;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="close" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Create Program</Text>
        <View style={styles.backBtn} />
      </View>

      {/* Progress */}
      <View style={styles.progressContainer}>
        {Array.from({ length: totalSteps }, (_, i) => i + 1).map((s) => (
          <View key={s} style={[styles.progressDot, s <= step && styles.progressDotActive]} />
        ))}
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
        {step === 4 && renderStep4()}
        {step === 5 && renderStep5()}
        {step === 6 && renderStep6()}
        {step === 7 && renderStep7()}
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
          onPress={step < totalSteps ? () => setStep(step + 1) : handleGenerate}
          disabled={loading || checkingSubscription}
        >
          {loading || checkingSubscription ? (
            <ActivityIndicator size="small" color={colors.textOnPrimary} />
          ) : (
            <>
              <Text style={styles.navNextText}>
                {step < totalSteps ? 'Continue' : 'Generate Program'}
              </Text>
              <Ionicons name={step < totalSteps ? "arrow-forward" : "sparkles"} size={20} color={colors.textOnPrimary} />
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
    gap: 6,
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
    width: 16,
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
  // Option Card (Goals, Splits)
  optionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 14,
    marginBottom: 10,
    borderWidth: 2,
    borderColor: colors.border,
  },
  optionCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  optionIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  optionIconActive: {
    backgroundColor: colors.primary,
  },
  optionContent: {
    flex: 1,
    marginLeft: 14,
  },
  optionLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  optionLabelActive: {
    color: colors.primary,
  },
  optionDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  // Training Style Grid
  styleGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  styleCard: {
    width: '47%',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
    position: 'relative',
  },
  styleCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  styleIconWrap: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  styleIconWrapActive: {
    backgroundColor: colors.primary,
  },
  styleLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  styleLabelActive: {
    color: colors.primary,
  },
  styleDesc: {
    fontSize: 12,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  checkBadge: {
    position: 'absolute',
    top: 10,
    right: 10,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Chips (Focus Areas, Equipment)
  chipContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: 25,
    backgroundColor: colors.surface,
    borderWidth: 2,
    borderColor: colors.border,
  },
  chipActive: {
    backgroundColor: colors.primary + '20',
    borderColor: colors.primary,
  },
  chipPrimary: {
    backgroundColor: colors.primary + '30',
    borderColor: colors.primary,
    borderWidth: 2.5,
  },
  chipFeatured: {
    borderColor: colors.primary + '50',
  },
  chipCheck: {
    marginRight: 6,
  },
  chipText: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  chipTextActive: {
    color: colors.primary,
  },
  // Focus area badges
  focusBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 16,
    flexWrap: 'wrap',
  },
  focusBadgePrimary: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: colors.primary,
    borderRadius: 20,
  },
  focusBadgePrimaryText: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.background,
  },
  focusBadgeSecondary: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    backgroundColor: colors.primary + '20',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.primary + '40',
  },
  focusBadgeSecondaryText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.primary,
  },
  // Duration Grid
  durationGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  durationCard: {
    width: '47%',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
  },
  durationCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  durationValue: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
  },
  durationValueActive: {
    color: colors.primary,
  },
  durationDesc: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  // Days
  daysContainer: {
    flexDirection: 'row',
    gap: 10,
  },
  dayBtn: {
    flex: 1,
    padding: 16,
    borderRadius: 12,
    backgroundColor: colors.surface,
    alignItems: 'center',
    borderWidth: 2,
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
  // Fitness Level
  levelContainer: {
    gap: 10,
  },
  levelCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 14,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: colors.border,
  },
  levelCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  levelIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  levelIconActive: {
    backgroundColor: colors.primary,
  },
  levelContent: {
    flex: 1,
    marginLeft: 12,
  },
  levelLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  levelLabelActive: {
    color: colors.primary,
  },
  levelDesc: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  // Text Input
  textInput: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: 16,
    fontSize: 16,
    color: colors.text,
    borderWidth: 2,
    borderColor: colors.border,
    minHeight: 80,
    textAlignVertical: 'top',
  },
  // Summary Card
  summaryCard: {
    backgroundColor: colors.surface,
    padding: 20,
    borderRadius: 16,
    marginTop: 24,
    borderWidth: 2,
    borderColor: colors.primary + '30',
  },
  summaryTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.primary,
    marginBottom: 16,
  },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  summaryIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primary + '15',
    justifyContent: 'center',
    alignItems: 'center',
  },
  summaryContent: {
    flex: 1,
    marginLeft: 12,
  },
  summaryLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  summaryValue: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
    marginTop: 2,
  },
  // Navigation
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
    color: colors.textOnPrimary,
  },
  btnDisabled: {
    opacity: 0.7,
  },
});
