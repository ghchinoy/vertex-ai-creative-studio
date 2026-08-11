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

package common

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strings"
	"testing"
)

// fakeGCS is an in-memory stand-in for a GCS bucket used to exercise the
// rename helpers without a live bucket or credentials. copyErrOn / deleteErrOn
// let a test inject a failure on a specific object.
type fakeGCS struct {
	objects     map[string]bool
	copyErrOn   string // if a copy targets this dst, fail
	deleteErr   error  // returned by every delete when non-nil
	deleteErrOn string // if a delete targets this object, fail with deleteErr
	copies      int
	deletes     int
}

func newFakeGCS(existing ...string) *fakeGCS {
	f := &fakeGCS{objects: map[string]bool{}}
	for _, o := range existing {
		f.objects[o] = true
	}
	return f
}

// install swaps the package-level seams to route through this fake and restores
// them when the test ends.
func (f *fakeGCS) install(t *testing.T) {
	t.Helper()
	origCopy, origDelete, origExists := copyGCSObjectFn, deleteGCSObjectFn, gcsObjectExistsFn
	copyGCSObjectFn = func(_ context.Context, _ /*bucket*/, src, dst string) error {
		f.copies++
		if f.copyErrOn != "" && dst == f.copyErrOn {
			return fmt.Errorf("injected copy failure for %s", dst)
		}
		if !f.objects[src] {
			return fmt.Errorf("source %s does not exist", src)
		}
		f.objects[dst] = true
		return nil
	}
	deleteGCSObjectFn = func(_ context.Context, _ /*bucket*/, obj string) error {
		f.deletes++
		if f.deleteErr != nil && (f.deleteErrOn == "" || obj == f.deleteErrOn) {
			return f.deleteErr
		}
		delete(f.objects, obj)
		return nil
	}
	gcsObjectExistsFn = func(_ context.Context, _ /*bucket*/, obj string) (bool, error) {
		return f.objects[obj], nil
	}
	t.Cleanup(func() {
		copyGCSObjectFn, deleteGCSObjectFn, gcsObjectExistsFn = origCopy, origDelete, origExists
	})
}

func (f *fakeGCS) list() []string {
	out := make([]string, 0, len(f.objects))
	for o := range f.objects {
		out = append(out, o)
	}
	sort.Strings(out)
	return out
}

// TestRenameGCSObjectSuccess: copy+delete both succeed → dst present, src gone.
func TestRenameGCSObjectSuccess(t *testing.T) {
	f := newFakeGCS("out/sample_0.png")
	f.install(t)

	if err := RenameGCSObject(context.Background(), "bkt", "out/sample_0.png", "out/hero.png"); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if f.objects["out/sample_0.png"] {
		t.Errorf("source object should have been deleted; objects=%v", f.list())
	}
	if !f.objects["out/hero.png"] {
		t.Errorf("destination object missing; objects=%v", f.list())
	}
}

// TestRenameGCSObjectCopyFailNoOrphan: copy fails → fatal error, source intact,
// no orphaned destination (cleanup delete of dst attempted).
func TestRenameGCSObjectCopyFailNoOrphan(t *testing.T) {
	f := newFakeGCS("out/sample_0.png")
	f.copyErrOn = "out/hero.png"
	f.install(t)

	err := RenameGCSObject(context.Background(), "bkt", "out/sample_0.png", "out/hero.png")
	if err == nil {
		t.Fatal("expected a fatal error on copy failure, got nil")
	}
	if f.objects["out/hero.png"] {
		t.Errorf("copy failure must leave NO orphaned destination; objects=%v", f.list())
	}
	if !f.objects["out/sample_0.png"] {
		t.Errorf("copy failure must leave the source intact; objects=%v", f.list())
	}
	if f.deletes == 0 {
		t.Errorf("expected a best-effort cleanup delete of the partial destination")
	}
}

// TestRenameGCSObjectDeleteFailNonFatal: copy succeeds, delete of source fails →
// nil returned (non-fatal), destination present.
func TestRenameGCSObjectDeleteFailNonFatal(t *testing.T) {
	f := newFakeGCS("out/sample_0.png")
	f.deleteErr = errors.New("injected delete failure")
	f.install(t)

	if err := RenameGCSObject(context.Background(), "bkt", "out/sample_0.png", "out/hero.png"); err != nil {
		t.Fatalf("delete failure must be non-fatal, got error: %v", err)
	}
	if !f.objects["out/hero.png"] {
		t.Errorf("destination object must be present after a non-fatal delete failure; objects=%v", f.list())
	}
	// The source remains (delete failed) — that is the accepted cosmetic leftover.
	if !f.objects["out/sample_0.png"] {
		t.Errorf("expected the source to remain after the delete failed; objects=%v", f.list())
	}
}

// TestRenameGCSObjectCollisionOverwrite: destination already exists → overwrite
// (no error). The pre-existing object is replaced by the copy.
func TestRenameGCSObjectCollisionOverwrite(t *testing.T) {
	f := newFakeGCS("out/sample_0.png", "out/hero.png")
	f.install(t)

	if err := RenameGCSObject(context.Background(), "bkt", "out/sample_0.png", "out/hero.png"); err != nil {
		t.Fatalf("collision should overwrite without error, got: %v", err)
	}
	if !f.objects["out/hero.png"] {
		t.Errorf("destination should exist after overwrite; objects=%v", f.list())
	}
	if f.objects["out/sample_0.png"] {
		t.Errorf("source should be gone after overwrite; objects=%v", f.list())
	}
}

// TestRenameGCSObjectSrcEqualsDst: a no-op rename returns nil and touches nothing.
func TestRenameGCSObjectSrcEqualsDst(t *testing.T) {
	f := newFakeGCS("out/hero.png")
	f.install(t)
	if err := RenameGCSObject(context.Background(), "bkt", "out/hero.png", "out/hero.png"); err != nil {
		t.Fatalf("src==dst should be a no-op, got: %v", err)
	}
	if f.copies != 0 || f.deletes != 0 {
		t.Errorf("src==dst should not copy or delete; copies=%d deletes=%d", f.copies, f.deletes)
	}
}

func TestRenameGCSObjectValidation(t *testing.T) {
	if err := RenameGCSObject(context.Background(), "", "s", "d"); err == nil {
		t.Error("expected error for empty bucket")
	}
	if err := RenameGCSObject(context.Background(), "bkt", "", "d"); err == nil {
		t.Error("expected error for empty src")
	}
	if err := RenameGCSObject(context.Background(), "bkt", "s", ""); err == nil {
		t.Error("expected error for empty dst")
	}
}

// TestRenameGCSObjectsBatchSuccess: all sample_* renamed, originals gone.
func TestRenameGCSObjectsBatchSuccess(t *testing.T) {
	f := newFakeGCS("out/sample_0.png", "out/sample_1.png", "out/sample_2.png", "out/sample_3.png")
	f.install(t)

	renames := []Rename{
		{Src: "out/sample_0.png", Dst: "out/hero_1.png"},
		{Src: "out/sample_1.png", Dst: "out/hero_2.png"},
		{Src: "out/sample_2.png", Dst: "out/hero_3.png"},
		{Src: "out/sample_3.png", Dst: "out/hero_4.png"},
	}
	renamed, err := RenameGCSObjects(context.Background(), "bkt", renames)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(renamed) != 4 {
		t.Fatalf("expected 4 renamed, got %d (%v)", len(renamed), renamed)
	}
	for _, o := range f.list() {
		if o == "out/sample_0.png" || o == "out/sample_1.png" || o == "out/sample_2.png" || o == "out/sample_3.png" {
			t.Errorf("all sample_* originals must be gone after a successful batch; found %s", o)
		}
	}
	want := []string{"out/hero_1.png", "out/hero_2.png", "out/hero_3.png", "out/hero_4.png"}
	if got := f.list(); !equalStrings(got, want) {
		t.Errorf("final objects = %v, want %v", got, want)
	}
}

// TestRenameGCSObjectsBatchPartialFailureNoRollback: a mid-batch copy failure
// returns the already-renamed dst names plus a fatal error, and does NOT roll
// back the already-renamed valid outputs.
func TestRenameGCSObjectsBatchPartialFailureNoRollback(t *testing.T) {
	f := newFakeGCS("out/sample_0.png", "out/sample_1.png", "out/sample_2.png")
	f.copyErrOn = "out/hero_2.png" // fail on the second rename
	f.install(t)

	renames := []Rename{
		{Src: "out/sample_0.png", Dst: "out/hero_1.png"},
		{Src: "out/sample_1.png", Dst: "out/hero_2.png"}, // fails here
		{Src: "out/sample_2.png", Dst: "out/hero_3.png"},
	}
	renamed, err := RenameGCSObjects(context.Background(), "bkt", renames)
	if err == nil {
		t.Fatal("expected a fatal error on mid-batch copy failure")
	}
	if len(renamed) != 1 || renamed[0] != "out/hero_1.png" {
		t.Fatalf("expected renamed-so-far = [out/hero_1.png], got %v", renamed)
	}
	// No rollback: the first, already-renamed valid output stays.
	if !f.objects["out/hero_1.png"] {
		t.Errorf("already-renamed valid output must NOT be rolled back; objects=%v", f.list())
	}
	// The failed artifact's source remains (named in the error for the caller).
	if !f.objects["out/sample_1.png"] {
		t.Errorf("failed artifact source should remain; objects=%v", f.list())
	}
	// The batch stopped: sample_2 was never processed.
	if !f.objects["out/sample_2.png"] {
		t.Errorf("batch should stop at first failure; sample_2 should be untouched; objects=%v", f.list())
	}
	if !strings.Contains(err.Error(), "out/sample_1.png") {
		t.Errorf("error should name the source left behind, got: %v", err)
	}
}

func equalStrings(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
