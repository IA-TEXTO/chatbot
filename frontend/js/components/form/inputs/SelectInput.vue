<script setup lang="ts">
import type { FormField } from "@/types/djangoForm";
defineProps<{ field: FormField }>();
</script>

<template>
    <select class="select w-full" :class="{ 'select-error': field.errors.length }" :id="field.id_for_label"
        :name="field.name" :disabled="field.disabled" v-bind="field.widget_attrs">
        <option>--------</option>
        <option v-for="choice in field.choices" :value="choice[0]" :selected="field.value == choice[0]">
            {{ choice[1] }}
        </option>
    </select>
</template>
