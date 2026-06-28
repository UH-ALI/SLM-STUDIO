'use client';

import { useState } from 'react';
import { Cpu, ChevronDown, ChevronUp } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { ModelCard } from '@/components/molecules/ModelCard';
import { Slider } from '@/components/atoms/Slider';
import { Button } from '@/components/atoms/Button';
import { WarningModal } from './WarningModal';
import type { Hyperparameters } from '@/types/project';

interface WizardConfigureProps {
  selectedModel: string;
  hyperparameters: Hyperparameters;
  onModelChange: (model: string) => void;
  onHyperparametersChange: (hp: Hyperparameters) => void;
  onStartTraining: () => void;
  onBack: () => void;
}

const models = [
  { name: 'Qwen 2.5 1.5B', description: 'Balanced performance and speed', value: 'qwen-2.5-1.5b' },
  { name: 'Qwen 2.5 0.5B', description: 'Faster training, lighter weight', value: 'qwen-2.5-0.5b' },
];

export function WizardConfigure({
  selectedModel,
  hyperparameters,
  onModelChange,
  onHyperparametersChange,
  onStartTraining,
  onBack,
}: WizardConfigureProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showWarning, setShowWarning] = useState(false);

  const handleAdvancedClick = () => {
    if (!showAdvanced) {
      setShowWarning(true);
    } else {
      setShowAdvanced(false);
    }
  };

  const handleWarningContinue = () => {
    setShowWarning(false);
    setShowAdvanced(true);
  };

  return (
    <div className="space-y-6">
      {/* Model Selection */}
      <div>
        <h3 className="text-sm font-semibold text-ivory mb-1">Select Model</h3>
        <p className="text-xs text-fern mb-3">Choose the base model for fine-tuning</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {models.map((model) => (
            <ModelCard
              key={model.value}
              name={model.name}
              description={model.description}
              selected={selectedModel === model.value}
              onClick={() => onModelChange(model.value)}
            />
          ))}
        </div>
      </div>

      {/* Advanced Settings */}
      <div>
        <button
          onClick={handleAdvancedClick}
          className={classNames(
            'w-full flex items-center justify-between p-3 rounded-xl',
            'bg-[#121B16]/60 border border-white/[0.08]',
            'hover:border-gold/20 transition-all',
            'focus-visible:outline-2 focus-visible:outline-gold focus-visible:outline-offset-2'
          )}
        >
          <span className="text-sm font-medium text-ivory">Advanced Settings</span>
          {showAdvanced ? (
            <ChevronUp size={18} className="text-fern" />
          ) : (
            <ChevronDown size={18} className="text-fern" />
          )}
        </button>

        {showAdvanced && (
          <div className="mt-4 space-y-6 p-4 rounded-xl bg-[#121B16]/40 border border-white/[0.04]">
            <Slider
              label="Creativity Control (Temperature)"
              value={hyperparameters.temperature !== undefined ? hyperparameters.temperature : 0.7}
              min={0.1}
              max={2.0}
              step={0.1}
              onChange={(v) => onHyperparametersChange({ ...hyperparameters, temperature: v })}
              formatValue={(v) => v.toFixed(1)}
            />
            <Slider
              label="Training Rounds (Epochs)"
              value={hyperparameters.epochs || 3}
              min={1}
              max={100}
              step={1}
              onChange={(v) => onHyperparametersChange({ ...hyperparameters, epochs: Math.round(v) })}
              formatValue={(v) => Math.round(v).toString()}
            />
            <Slider
              label="Learning Speed (LR)"
              value={hyperparameters.learningRate || 0.0002}
              min={0.000001}
              max={0.001}
              step={0.000001}
              onChange={(v) => onHyperparametersChange({ ...hyperparameters, learningRate: v })}
              formatValue={(v) => v.toExponential(0)}
            />
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex justify-between pt-4">
        <Button variant="secondary" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onStartTraining} icon={Cpu}>
          Start Training
        </Button>
      </div>

      {/* Warning Modal */}
      {showWarning && (
        <WarningModal
          onCancel={() => setShowWarning(false)}
          onContinue={handleWarningContinue}
        />
      )}
    </div>
  );
}
