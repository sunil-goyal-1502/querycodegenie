
import React, { useState } from 'react';
import { Folder, File, ChevronRight, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

type FileNode = {
  type: 'file';
  language: string;
  path: string;
};

type DirectoryNode = {
  type: 'directory';
  children: Record<string, FileNode | DirectoryNode>;
};

type FileTreeNode = FileNode | DirectoryNode;

type FileTreeProps = {
  structure: Record<string, FileTreeNode>;
  onFileSelect: (path: string) => void;
  selectedFile?: string;
  className?: string;
};

export function FileExplorer({ structure, onFileSelect, selectedFile, className }: FileTreeProps) {
  return (
    <div className={cn("px-2 py-2 h-full overflow-auto", className)}>
      <h3 className="text-sm font-medium mb-2 text-muted-foreground">Files</h3>
      <FileTreeNode 
        name="" 
        node={structure} 
        level={0} 
        onFileSelect={onFileSelect} 
        selectedFile={selectedFile}
        expandedByDefault={true}
      />
    </div>
  );
}

type FileTreeNodeProps = {
  name: string;
  node: Record<string, FileTreeNode> | FileTreeNode;
  level: number;
  onFileSelect: (path: string) => void;
  selectedFile?: string;
  expandedByDefault?: boolean;
};

function FileTreeNode({ name, node, level, onFileSelect, selectedFile, expandedByDefault = false }: FileTreeNodeProps) {
  const [expanded, setExpanded] = useState(expandedByDefault);

  if (!node) return null;

  // If this is the root node or a directory node with children property
  if (name === '' || (node as DirectoryNode).children) {
    // For root node or directory nodes
    const children = name === '' ? (node as Record<string, FileTreeNode>) : (node as DirectoryNode).children;
    const sortedItems = Object.entries(children).sort((a, b) => {
      // Sort directories first, then files
      const aIsDir = a[1].type === 'directory';
      const bIsDir = b[1].type === 'directory';
      
      if (aIsDir && !bIsDir) return -1;
      if (!aIsDir && bIsDir) return 1;
      
      // Then sort alphabetically
      return a[0].localeCompare(b[0]);
    });

    // For the root node, just render children without a directory header
    if (name === '') {
      return (
        <>
          {sortedItems.map(([childName, childNode]) => (
            <FileTreeNode
              key={childName}
              name={childName}
              node={childNode}
              level={level}
              onFileSelect={onFileSelect}
              selectedFile={selectedFile}
              expandedByDefault={level === 0}
            />
          ))}
        </>
      );
    }

    // For regular directory nodes
    return (
      <div>
        <div 
          className="flex items-center py-1 cursor-pointer hover:bg-accent hover:text-accent-foreground rounded px-1"
          onClick={() => setExpanded(!expanded)}
          style={{ paddingLeft: `${level * 12}px` }}
        >
          {expanded ? <ChevronDown className="h-4 w-4 mr-1" /> : <ChevronRight className="h-4 w-4 mr-1" />}
          <Folder className="h-4 w-4 mr-2 text-blue-400" />
          <span className="text-sm truncate">{name}</span>
        </div>
        
        {expanded && (
          <div>
            {sortedItems.map(([childName, childNode]) => (
              <FileTreeNode
                key={childName}
                name={childName}
                node={childNode}
                level={level + 1}
                onFileSelect={onFileSelect}
                selectedFile={selectedFile}
              />
            ))}
          </div>
        )}
      </div>
    );
  } else {
    // For file nodes
    const fileNode = node as FileNode;
    const isSelected = selectedFile === fileNode.path;
    
    return (
      <div
        className={cn(
          "flex items-center py-1 px-1 rounded cursor-pointer hover:bg-accent hover:text-accent-foreground",
          isSelected && "bg-accent text-accent-foreground"
        )}
        style={{ paddingLeft: `${level * 12}px` }}
        onClick={() => onFileSelect(fileNode.path)}
      >
        <File className="h-4 w-4 mr-2 text-gray-400" />
        <span className="text-sm truncate">{name}</span>
      </div>
    );
  }
}

export default FileExplorer;
