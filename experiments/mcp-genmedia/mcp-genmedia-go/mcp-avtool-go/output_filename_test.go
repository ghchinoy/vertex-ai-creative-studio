// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import "testing"

// TestResolveAVToolOutputFilename covers the avtool naming decision: output_filename
// wins over the deprecated output_file_name alias; the client-provided extension is
// PRESERVED (avtool is exempt from extension-forcing, design §4d); traversal is
// sanitized; and an empty/unusable value falls through to the unique-name default.
func TestResolveAVToolOutputFilename(t *testing.T) {
	tests := []struct {
		name    string
		argsMap map[string]interface{}
		want    string
	}{
		{
			name:    "output_filename honored, extension preserved",
			argsMap: map[string]interface{}{"output_filename": "converted.mp3"},
			want:    "converted.mp3",
		},
		{
			name:    "arbitrary client extension preserved (no forcing)",
			argsMap: map[string]interface{}{"output_filename": "clip.mkv"},
			want:    "clip.mkv",
		},
		{
			name:    "legacy output_file_name used when output_filename unset",
			argsMap: map[string]interface{}{"output_file_name": "legacy.mp4"},
			want:    "legacy.mp4",
		},
		{
			name: "output_filename wins over legacy output_file_name",
			argsMap: map[string]interface{}{
				"output_filename":  "new.mp4",
				"output_file_name": "legacy.mp4",
			},
			want: "new.mp4",
		},
		{
			name:    "traversal sanitized, extension kept",
			argsMap: map[string]interface{}{"output_filename": "../../etc/out.gif"},
			want:    "out.gif",
		},
		{
			name:    "unset -> empty (unique-name default)",
			argsMap: map[string]interface{}{},
			want:    "",
		},
		{
			name:    "dot-only sanitizes to empty (unique-name default)",
			argsMap: map[string]interface{}{"output_filename": "..."},
			want:    "",
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if got := resolveAVToolOutputFilename(tc.argsMap); got != tc.want {
				t.Errorf("resolveAVToolOutputFilename(%v) = %q, want %q", tc.argsMap, got, tc.want)
			}
		})
	}
}
