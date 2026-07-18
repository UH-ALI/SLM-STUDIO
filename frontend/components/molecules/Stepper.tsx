import { classNames } from '@/lib/utils';
import { Check } from 'lucide-react';

interface Step {
  label: string;
  description?: string;
}

interface StepperProps {
  steps: Step[];
  currentStep: number;
  className?: string;
}

export function Stepper({ steps, currentStep, className }: StepperProps) {
  return (
    <div className={classNames('w-full', className)}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-0">
        {steps.map((step, index) => {
          const isCompleted = index < currentStep;
          const isActive = index === currentStep;
          const isUpcoming = index > currentStep;

          return (
            <div key={index} className="flex items-start sm:items-center flex-1 last:flex-none">
              {/* Step indicator */}
              <div className="flex flex-row sm:flex-col items-center sm:items-center gap-3 sm:gap-0">
                <div
                  className={classNames(
                    'w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-500 ease-brand border-2',
                    isCompleted && 'bg-gradient-to-br from-gold to-sage border-transparent text-void',
                    isActive && 'bg-void border-gold text-gold shadow-[0_0_0_4px_rgba(212,168,83,0.15)]',
                    isUpcoming && 'bg-void border-white/[0.12] text-muted'
                  )}
                >
                  {isCompleted ? (
                    <Check size={16} strokeWidth={3} />
                  ) : (
                    <span>{index + 1}</span>
                  )}
                </div>
                <div className="sm:text-center">
                  <span
                    className={classNames(
                      'text-xs font-medium whitespace-nowrap transition-colors duration-300',
                      isActive ? 'text-gold' : isCompleted ? 'text-ivory' : 'text-muted'
                    )}
                  >
                    {step.label}
                  </span>
                  {step.description && (
                    <p className="hidden sm:block mt-1 text-[0.65rem] text-muted max-w-[120px] leading-snug">
                      {step.description}
                    </p>
                  )}
                </div>
              </div>

              {/* Connector line */}
              {index < steps.length - 1 && (
                <div className="hidden sm:block flex-1 h-px mx-4 -mt-5 bg-white/[0.06]">
                  <div
                    className={classNames(
                      'h-full bg-gradient-to-r from-gold to-sage transition-all duration-500 ease-brand',
                      isCompleted ? 'w-full' : 'w-0'
                    )}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
