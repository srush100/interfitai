import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Image,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';

interface AnalysisResult {
  overall_assessment: string;
  visible_changes: string[];
  areas_improved: string[];
  recommendations: string[];
  motivation_message: string;
  estimated_progress_score: number;
}

export default function BodyAnalyzer() {
  const router = useRouter();
  const { profile } = useUserStore();
  const [beforeImage, setBeforeImage] = useState<string | null>(null);
  const [afterImage, setAfterImage] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [timePeriod, setTimePeriod] = useState('3 months');

  const TIME_PERIODS = ['1 month', '3 months', '6 months', '1 year'];

  const pickImage = async (type: 'before' | 'after') => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission needed', 'Please grant camera roll permissions');
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [3, 4],
      quality: 0.5,
      base64: true,
    });

    if (!result.canceled && result.assets[0].base64) {
      if (type === 'before') {
        setBeforeImage(result.assets[0].base64);
      } else {
        setAfterImage(result.assets[0].base64);
      }
    }
  };

  const takePhoto = async (type: 'before' | 'after') => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission needed', 'Please grant camera permissions');
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: true,
      aspect: [3, 4],
      quality: 0.5,
      base64: true,
    });

    if (!result.canceled && result.assets[0].base64) {
      if (type === 'before') {
        setBeforeImage(result.assets[0].base64);
      } else {
        setAfterImage(result.assets[0].base64);
      }
    }
  };

  const analyzeProgress = async () => {
    if (!beforeImage || !afterImage || !profile?.id) {
      Alert.alert('Missing Photos', 'Please upload both before and after photos');
      return;
    }

    setAnalyzing(true);
    setAnalysis(null);

    try {
      const response = await api.post('/body/analyze', {
        user_id: profile.id,
        before_image_base64: beforeImage,
        after_image_base64: afterImage,
        time_period: timePeriod,
      });

      setAnalysis(response.data.analysis);
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to analyze progress');
    } finally {
      setAnalyzing(false);
    }
  };

  const resetAnalysis = () => {
    setBeforeImage(null);
    setAfterImage(null);
    setAnalysis(null);
  };

  const renderPhotoUpload = (type: 'before' | 'after', image: string | null) => (
    <View style={styles.photoContainer}>
      <Text style={styles.photoLabel}>{type === 'before' ? 'Before' : 'After'}</Text>
      {image ? (
        <View style={styles.imageWrapper}>
          <Image
            source={{ uri: `data:image/jpeg;base64,${image}` }}
            style={styles.progressImage}
          />
          <TouchableOpacity
            style={styles.removeBtn}
            onPress={() => type === 'before' ? setBeforeImage(null) : setAfterImage(null)}
          >
            <Ionicons name="close-circle" size={28} color={colors.error} />
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.uploadPlaceholder}>
          <Ionicons name="body" size={40} color={colors.textMuted} />
          <Text style={styles.uploadText}>Add {type} photo</Text>
          <View style={styles.uploadActions}>
            <TouchableOpacity
              style={styles.uploadBtn}
              onPress={() => pickImage(type)}
            >
              <Ionicons name="images" size={18} color={colors.primary} />
              <Text style={styles.uploadBtnText}>Gallery</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.uploadBtn}
              onPress={() => takePhoto(type)}
            >
              <Ionicons name="camera" size={18} color={colors.primary} />
              <Text style={styles.uploadBtnText}>Camera</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Body Analyzer</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {!analysis ? (
          <>
            {/* Instructions */}
            <View style={styles.infoCard}>
              <Ionicons name="sparkles" size={24} color={colors.primary} />
              <Text style={styles.infoTitle}>AI Progress Analysis</Text>
              <Text style={styles.infoText}>
                Upload before & after photos to get AI-powered insights on your body transformation journey.
              </Text>
            </View>

            {/* Time Period Selector */}
            <Text style={styles.sectionLabel}>Time Between Photos</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.periodContainer}>
              {TIME_PERIODS.map((period) => (
                <TouchableOpacity
                  key={period}
                  style={[styles.periodBtn, timePeriod === period && styles.periodBtnActive]}
                  onPress={() => setTimePeriod(period)}
                >
                  <Text style={[styles.periodText, timePeriod === period && styles.periodTextActive]}>
                    {period}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            {/* Photo Upload */}
            <View style={styles.photosRow}>
              {renderPhotoUpload('before', beforeImage)}
              {renderPhotoUpload('after', afterImage)}
            </View>

            {/* Analyze Button */}
            <TouchableOpacity
              style={[
                styles.analyzeBtn,
                (!beforeImage || !afterImage) && styles.analyzeBtnDisabled,
              ]}
              onPress={analyzeProgress}
              disabled={!beforeImage || !afterImage || analyzing}
            >
              {analyzing ? (
                <ActivityIndicator size="small" color={colors.background} />
              ) : (
                <>
                  <Ionicons name="analytics" size={22} color={colors.background} />
                  <Text style={styles.analyzeBtnText}>Analyze Transformation</Text>
                </>
              )}
            </TouchableOpacity>
          </>
        ) : (
          <>
            {/* Analysis Results */}
            <View style={styles.resultsCard}>
              <View style={styles.scoreContainer}>
                <View style={styles.scoreCircle}>
                  <Text style={styles.scoreValue}>{analysis.estimated_progress_score}</Text>
                  <Text style={styles.scoreMax}>/10</Text>
                </View>
                <Text style={styles.scoreLabel}>Progress Score</Text>
              </View>

              <Text style={styles.assessmentTitle}>Overall Assessment</Text>
              <Text style={styles.assessmentText}>{analysis.overall_assessment}</Text>

              <View style={styles.divider} />

              <Text style={styles.sectionTitle}>Visible Changes</Text>
              {analysis.visible_changes.map((change, idx) => (
                <View key={idx} style={styles.listItem}>
                  <Ionicons name="checkmark-circle" size={18} color={colors.success} />
                  <Text style={styles.listText}>{change}</Text>
                </View>
              ))}

              <View style={styles.divider} />

              <Text style={styles.sectionTitle}>Areas Improved</Text>
              <View style={styles.tagsContainer}>
                {analysis.areas_improved.map((area, idx) => (
                  <View key={idx} style={styles.tag}>
                    <Text style={styles.tagText}>{area}</Text>
                  </View>
                ))}
              </View>

              <View style={styles.divider} />

              <Text style={styles.sectionTitle}>Recommendations</Text>
              {analysis.recommendations.map((rec, idx) => (
                <View key={idx} style={styles.listItem}>
                  <Text style={styles.recNumber}>{idx + 1}</Text>
                  <Text style={styles.listText}>{rec}</Text>
                </View>
              ))}

              <View style={styles.motivationCard}>
                <Ionicons name="heart" size={24} color={colors.primary} />
                <Text style={styles.motivationText}>{analysis.motivation_message}</Text>
              </View>
            </View>

            <TouchableOpacity style={styles.resetBtn} onPress={resetAnalysis}>
              <Ionicons name="refresh" size={20} color={colors.text} />
              <Text style={styles.resetBtnText}>Analyze New Photos</Text>
            </TouchableOpacity>
          </>
        )}
      </ScrollView>
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
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  infoCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
    marginBottom: 24,
  },
  infoTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
    marginTop: 12,
  },
  infoText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20,
  },
  sectionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 12,
  },
  periodContainer: {
    marginBottom: 24,
  },
  periodBtn: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: colors.surface,
    marginRight: 10,
  },
  periodBtnActive: {
    backgroundColor: colors.primary,
  },
  periodText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  periodTextActive: {
    color: colors.background,
  },
  photosRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 24,
  },
  photoContainer: {
    flex: 1,
  },
  photoLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 8,
    textAlign: 'center',
  },
  imageWrapper: {
    position: 'relative',
  },
  progressImage: {
    width: '100%',
    aspectRatio: 0.75,
    borderRadius: 12,
  },
  removeBtn: {
    position: 'absolute',
    top: -8,
    right: -8,
    backgroundColor: colors.background,
    borderRadius: 14,
  },
  uploadPlaceholder: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    aspectRatio: 0.75,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: colors.border,
    borderStyle: 'dashed',
  },
  uploadText: {
    fontSize: 13,
    color: colors.textMuted,
    marginTop: 8,
  },
  uploadActions: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 12,
  },
  uploadBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: colors.primary + '20',
  },
  uploadBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.primary,
  },
  analyzeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: colors.primary,
    padding: 18,
    borderRadius: 16,
  },
  analyzeBtnDisabled: {
    backgroundColor: colors.surfaceLight,
  },
  analyzeBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.background,
  },
  resultsCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 24,
    marginBottom: 16,
  },
  scoreContainer: {
    alignItems: 'center',
    marginBottom: 24,
  },
  scoreCircle: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
    flexDirection: 'row',
  },
  scoreValue: {
    fontSize: 36,
    fontWeight: '700',
    color: colors.primary,
  },
  scoreMax: {
    fontSize: 18,
    color: colors.textSecondary,
    marginTop: 8,
  },
  scoreLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 8,
  },
  assessmentTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 8,
  },
  assessmentText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: 20,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 12,
  },
  listItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginBottom: 10,
  },
  listText: {
    flex: 1,
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
  recNumber: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.primary + '20',
    textAlign: 'center',
    lineHeight: 22,
    fontSize: 12,
    fontWeight: '700',
    color: colors.primary,
  },
  tagsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tag: {
    backgroundColor: colors.success + '20',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  tagText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.success,
  },
  motivationCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    backgroundColor: colors.primary + '15',
    padding: 16,
    borderRadius: 12,
    marginTop: 20,
  },
  motivationText: {
    flex: 1,
    fontSize: 14,
    color: colors.text,
    lineHeight: 22,
    fontStyle: 'italic',
  },
  resetBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 12,
  },
  resetBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
});
