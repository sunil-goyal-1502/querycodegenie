
import React from 'react';
import { Progress } from '@/components/ui/progress';
import { CircleCheck, AlertCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

type CodeProgressProps = {
  isIndexing: boolean;
  progress: number;
  message: string;
  error: string | null;
  stats: {
    total_files?: number;
    indexed_files?: number;
    skipped_files?: number;
    binary_files?: number;
    by_language?: Record<string, number>;
  };
  className?: string;
};

export function CodeProgress({ isIndexing, progress, message, error, stats, className }: CodeProgressProps) {
  return (
    <div className={cn("p-4 rounded-lg border bg-card", className)}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-lg font-medium flex items-center gap-2">
          {isIndexing ? (
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          ) : error ? (
            <AlertCircle className="h-5 w-5 text-destructive" />
          ) : progress === 100 ? (
            <CircleCheck className="h-5 w-5 text-primary" />
          ) : (
            <Loader2 className="h-5 w-5 text-muted-foreground" />
          )}
          Code Indexing Status
        </h3>
        {isIndexing && (
          <span className="text-sm text-muted-foreground">{progress}%</span>
        )}
      </div>
      
      <Progress value={progress} className="h-2 mb-4" />
      
      <div className="text-sm mb-3">{message}</div>
      
      {error && (
        <div className="text-sm text-destructive bg-destructive/10 p-2 rounded mb-3">
          {error}
        </div>
      )}
      
      {progress === 100 && !error && stats.indexed_files && (
        <div className="bg-muted rounded-md p-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Total Files</div>
              <div className="text-lg font-medium">{stats.total_files}</div>
            </div>
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Indexed</div>
              <div className="text-lg font-medium">{stats.indexed_files}</div>
            </div>
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Skipped</div>
              <div className="text-lg font-medium">{stats.skipped_files}</div>
            </div>
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Binary Files</div>
              <div className="text-lg font-medium">{stats.binary_files}</div>
            </div>
          </div>
          
          {stats.by_language && Object.keys(stats.by_language).length > 0 && (
            <div>
              <div className="text-xs text-muted-foreground mb-2">Languages</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(stats.by_language)
                  .filter(([lang]) => lang !== 'unknown')
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 10)
                  .map(([language, count]) => (
                    <div key={language} className="text-xs bg-background border rounded-full px-2 py-1">
                      {language}: {count}
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default CodeProgress;
