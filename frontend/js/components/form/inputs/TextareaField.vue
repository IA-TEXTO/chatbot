<script setup lang="ts">
import type { FormField } from "@/types/djangoForm";
defineProps<{ field: FormField }>();
</script>

<template>
    <textarea
        class="textarea textarea-bordered w-full"
        :class="{ 'textarea-error': field.errors.length }"
        :id="field.id_for_label"
        :name="field.name"
        :disabled="field.disabled"
        v-bind="field.widget_attrs"
    >{{ field.value }}</textarea>
</template>
