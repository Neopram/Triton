import React, { useState } from 'react';
import { Star, StarHalf } from 'lucide-react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import useInsightStore from '../store/insightStore';

interface InsightFeedbackProps {
  insightId: number;
  currentRating?: number;
  currentFeedback?: string;
  onFeedbackSubmitted?: () => void;
}

const InsightFeedback: React.FC<InsightFeedbackProps> = ({
  insightId,
  currentRating,
  currentFeedback,
  onFeedbackSubmitted
}) => {
  const [rating, setRating] = useState<number>(currentRating || 0);
  const [feedback, setFeedback] = useState<string>(currentFeedback || '');
  const [hoveredRating, setHoveredRating] = useState<number>(0);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const { submitFeedback } = useInsightStore();

  const handleRatingClick = (value: number) => {
    setRating(value);
  };

  const handleSubmit = async () => {
    if (rating === 0) return;
    
    setIsSubmitting(true);
    const success = await submitFeedback(insightId, rating, feedback);
    setIsSubmitting(false);
    
    if (success && onFeedbackSubmitted) {
      onFeedbackSubmitted();
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium mb-2">Rate this insight:</h3>
        <div className="flex space-x-1">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              key={value}
              className="text-2xl focus:outline-none"
              onMouseEnter={() => setHoveredRating(value)}
              onMouseLeave={() => setHoveredRating(0)}
              onClick={() => handleRatingClick(value)}
            >
              <Star
                fill={
                  (hoveredRating ? hoveredRating >= value : rating >= value)
                    ? '#f59e0b'
                    : 'none'
                }
                color={
                  (hoveredRating ? hoveredRating >= value : rating >= value)
                    ? '#f59e0b'
                    : '#d1d5db'
                }
                size={24}
              />
            </button>
          ))}
          <span className="ml-2 text-sm text-gray-500">
            {rating > 0 ? `${rating} of 5` : 'Not rated'}
          </span>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium mb-2">Additional feedback (optional):</h3>
        <Textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="Share your thoughts on this insight..."
          className="min-h-[100px]"
        />
      </div>

      <Button 
        onClick={handleSubmit} 
        disabled={rating === 0 || isSubmitting}
        className="w-full"
      >
        {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
      </Button>
    </div>
  );
};

export default InsightFeedback;